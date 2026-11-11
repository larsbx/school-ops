import Release
open SchoolOps.Release

private def bit (mask position : Nat) : Bool := mask / (2 ^ position) % 2 == 1
private def checks (mask : Nat) : Checks :=
  ⟨bit mask 0, bit mask 1, bit mask 2, bit mask 3,
   bit mask 4, bit mask 5, bit mask 6, bit mask 7⟩

def main : IO Unit := do
  for mask in List.range 256 do
    IO.println s!"{mask}:{admitted (checks mask)}"
