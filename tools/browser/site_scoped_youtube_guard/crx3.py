"""Restricted, deterministic developer-signed CRX3 profile using OpenSSL.

This implements one RSA proof, not the Chrome Web Store publisher-proof profile.
OpenSSL is a local signing/verification tool, never supplied by a release bundle.
No private key bytes are copied into release artifacts or diagnostic output.
"""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile


MAX_ZIP_BYTES = 8 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
MAX_CRX_BYTES = MAX_ZIP_BYTES + MAX_HEADER_BYTES + 12
SIGNATURE_CONTEXT = b"CRX3 SignedData\x00"
RSA_OID = bytes.fromhex("06092a864886f70d010101")


def openssl(args, data=None):
    """No shell, interactive password input, or stderr containing key paths."""
    try:
        result = subprocess.run(["openssl", *args], input=data if data is not None else b"",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=30, check=False)
    except FileNotFoundError as exc:
        raise ValueError("Install OpenSSL 3 on this signing/verification workstation") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("OpenSSL did not complete within 30 seconds") from exc
    if result.returncode:
        raise ValueError("OpenSSL rejected the key, signature, or requested operation")
    return result.stdout


def read_file(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected a regular local file")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("File exceeds the supported size limit")
    return data


def _tlv(data, offset=0):
    """Small strict DER reader for a public RSA SubjectPublicKeyInfo."""
    start = offset
    if offset + 2 > len(data):
        raise ValueError("Truncated DER public key")
    tag, size = data[offset:offset + 2]
    offset += 2
    if size & 0x80:
        count = size & 0x7f
        if not 1 <= count <= 4 or offset + count > len(data) or data[offset] == 0:
            raise ValueError("Noncanonical DER length")
        size = int.from_bytes(data[offset:offset + count], "big")
        if size < 128:
            raise ValueError("Noncanonical DER length")
        offset += count
    end = offset + size
    if end > len(data):
        raise ValueError("Truncated DER public key")
    return tag, data[offset:end], end, data[start:end]


def _integer(data):
    if not data or data[0] & 0x80 or (len(data) > 1 and data[0] == 0 and not data[1] & 0x80):
        raise ValueError("Noncanonical RSA integer")
    return int.from_bytes(data, "big")


def validate_public_key(der):
    if not isinstance(der, bytes) or not 256 <= len(der) <= 2048:
        raise ValueError("Expected a DER RSA public key (2048–8192 bits)")
    tag, outer, end, _ = _tlv(der)
    if tag != 0x30 or end != len(der):
        raise ValueError("Expected exactly one DER SubjectPublicKeyInfo")
    tag, algorithm, offset, _ = _tlv(outer)
    if tag != 0x30 or algorithm != RSA_OID + b"\x05\x00":
        raise ValueError("Only RSA encryption public keys support this CRX3 profile")
    tag, bits, end, _ = _tlv(outer, offset)
    if tag != 3 or end != len(outer) or not bits or bits[0] != 0:
        raise ValueError("Invalid RSA public-key bit string")
    tag, rsa, end, _ = _tlv(bits[1:])
    if tag != 0x30 or end != len(bits) - 1:
        raise ValueError("Invalid RSA public key")
    tag, modulus, offset, _ = _tlv(rsa)
    etag, exponent, end, _ = _tlv(rsa, offset)
    if tag != 2 or etag != 2 or end != len(rsa):
        raise ValueError("Invalid RSA public key integers")
    n, e = _integer(modulus), _integer(exponent)
    if not 2048 <= n.bit_length() <= 8192 or n % 2 != 1 or e < 3 or e % 2 != 1:
        raise ValueError("RSA public key must be 2048–8192 bits with an odd exponent")
    return (n.bit_length() + 7) // 8


def public_key_bytes(path):
    raw = read_file(path, 16384)
    if b"PRIVATE KEY" in raw:
        raise ValueError("Preparation accepts only a public key; keep private keys with the signer")
    if raw.startswith(b"-----BEGIN PUBLIC KEY-----"):
        der = openssl(["pkey", "-pubin", "-inform", "PEM", "-outform", "DER"], raw)
    else:
        der = raw
    validate_public_key(der)
    return der


def extension_id(der):
    validate_public_key(der)
    return "".join(chr(ord("a") + int(c, 16)) for c in hashlib.sha256(der).hexdigest()[:32])


def _varint(value):
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def _field(number, value):
    return _varint((number << 3) | 2) + _varint(len(value)) + value


def _read_varint(data, offset):
    start, value = offset, 0
    for shift in range(0, 35, 7):
        if offset >= len(data):
            break
        byte = data[offset]
        value |= (byte & 127) << shift
        offset += 1
        if not byte & 128:
            if _varint(value) != data[start:offset]:
                raise ValueError("Noncanonical protobuf integer")
            return value, offset
    raise ValueError("Invalid protobuf integer")


def _fields(data, allowed):
    offset, result = 0, {}
    while offset < len(data):
        wire, offset = _read_varint(data, offset)
        number = wire >> 3
        if wire & 7 != 2 or number not in allowed or number in result:
            raise ValueError("Unexpected or duplicate CRX3 protobuf field")
        size, offset = _read_varint(data, offset)
        if size > len(data) - offset:
            raise ValueError("Truncated CRX3 protobuf field")
        result[number] = data[offset:offset + size]
        offset += size
    if set(result) != set(allowed):
        raise ValueError("Missing CRX3 protobuf field")
    return result


def signed_header(der):
    validate_public_key(der)
    return _field(1, hashlib.sha256(der).digest()[:16])


def signing_input(zip_bytes, der):
    if not zip_bytes.startswith(b"PK\x03\x04") or len(zip_bytes) > MAX_ZIP_BYTES:
        raise ValueError("Unsupported ZIP payload")
    header = signed_header(der)
    return SIGNATURE_CONTEXT + struct.pack("<I", len(header)) + header + zip_bytes


def verify_signature(payload, der, signature):
    size = validate_public_key(der)
    if len(signature) != size:
        raise ValueError("RSA signature has the wrong size")
    with tempfile.TemporaryDirectory(prefix="schoolops-crx-verify-") as td:
        key, sig = Path(td) / "public.der", Path(td) / "signature.bin"
        key.write_bytes(der)
        sig.write_bytes(signature)
        openssl(["dgst", "-sha256", "-verify", str(key), "-keyform", "DER",
                 "-sigopt", "rsa_padding_mode:pkcs1", "-signature", str(sig)], payload)


def sign_payload(payload, key_path):
    """Explicit local key integration. No passphrases accepted or persisted here.

    External/HSM signers can instead sign signing-input.bin and use assemble.
    """
    key = Path(key_path).expanduser().absolute()
    if key.is_symlink() or not key.is_file():
        raise ValueError("Signing key must be a regular local file")
    return openssl(["dgst", "-sha256", "-sign", str(key), "-passin", "pass:",
                    "-sigopt", "rsa_padding_mode:pkcs1"], payload)


def assemble(zip_bytes, der, signature):
    verify_signature(signing_input(zip_bytes, der), der, signature)
    proof = _field(1, der) + _field(2, signature)
    header = _field(2, proof) + _field(10000, signed_header(der))
    for marker in (b"PK\x05\x06", b"PK\x06\x07", b"PK\x06\x06"):
        if marker in header:
            raise ValueError("CRX3 header contains a forbidden ZIP end-record marker")
    return b"Cr24" + struct.pack("<II", 3, len(header)) + header + zip_bytes


def verify(crx, *, expected_zip, expected_key, expected_id):
    if len(crx) < 12 or len(crx) > MAX_CRX_BYTES or crx[:4] != b"Cr24":
        raise ValueError("Invalid CRX3 magic or size")
    version, header_size = struct.unpack("<II", crx[4:12])
    if version != 3 or not 0 < header_size <= MAX_HEADER_BYTES or 12 + header_size >= len(crx):
        raise ValueError("Invalid CRX3 format version or header size")
    header = crx[12:12 + header_size]
    if any(marker in header for marker in (b"PK\x05\x06", b"PK\x06\x07", b"PK\x06\x06")):
        raise ValueError("CRX3 header contains a forbidden ZIP end-record marker")
    fields = _fields(header, {2, 10000})
    proof = _fields(fields[2], {1, 2})
    signed = _fields(fields[10000], {1})
    der = proof[1]
    actual_id = extension_id(der)
    if der != expected_key or actual_id != expected_id:
        raise ValueError("CRX signing identity differs from the pinned extension ID/public key")
    if signed[1] != hashlib.sha256(der).digest()[:16]:
        raise ValueError("CRX signed extension ID differs from the signing key")
    archive = crx[12 + header_size:]
    if archive != expected_zip:
        raise ValueError("CRX ZIP fingerprint differs from the exact prepared configuration")
    payload = SIGNATURE_CONTEXT + struct.pack("<I", len(fields[10000])) + fields[10000] + archive
    verify_signature(payload, der, proof[2])
    # This deliberately supports only the canonical, single-proof release profile.
    if crx != assemble(expected_zip, expected_key, proof[2]):
        raise ValueError("CRX encoding differs from the supported canonical profile")
    return {"extension_id": actual_id, "extension_zip_sha256": hashlib.sha256(archive).hexdigest(),
            "crx_sha256": hashlib.sha256(crx).hexdigest(), "size": len(crx)}
