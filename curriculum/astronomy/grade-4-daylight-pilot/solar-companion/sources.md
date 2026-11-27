# Sources, calculations and scientific limits

**Review proposal; not source-admission or teaching approval.** Retrieval and
engineering checks were performed on 26 November 2026. External documentation
is linked and paraphrased; the lesson prose and exercises are original.

## Evidence ledger

| Layer | What is available | What it establishes |
| --- | --- | --- |
| Primary numerical source | Eight original NASA/JPL Horizons HTTP JSON responses, matching decoded text and request receipts | Reproducible calculated Sun azimuth/elevation at the requested reference points and times |
| Source identity | Complete URLs/parameters, response headers, UTC retrieval times, API signature 1.2, SHA-256 and returned model/site headers | Saved byte identity and consistency with the recorded retrieval; a hash is not a provider digital signature or independent authenticity proof |
| Author extraction | Four complete one-minute days and eight exact half-minute samples | Deterministic extraction of sixteen selected bearings and eight conventional horizon-crossing event labels |
| Independent provider check | A disclosed transcription of the successfully retrieved USNO Greenwich annual-table row | Four Greenwich event labels agree at displayed-minute precision; no independent Sydney/bearing-service result was obtained |
| Learner transformations | Minutes arithmetic, 15-degree representation and two deliberate omissions | Defined educational representations, not more precise physics or observed learner attainment |

The machine-readable [manifest](data/manifest.json) binds all source/receipt/text
hashes. [Extracted ephemerides](data/ephemerides.json) retain UTC/local dates,
original decimal strings, elevations, event brackets, midpoint values and source
identifiers. [Learner projection](data/learner-records.json) has no hidden value
for its deliberately withheld bearing. [Numerical keys](data/answers.json) are
teacher-facing; the prose/rhetoric criteria still need human assessment.

## Public reference inputs and clocks

| Input | Greenwich public reference | Sydney Observatory Hill reference |
| --- | --- | --- |
| Latitude, north positive | 51.4769 degrees | -33.86 degrees |
| Longitude, east positive | 0.0 degrees | 151.21 degrees |
| JPL geodetic reference height | 0 km above reference ellipsoid | 0 km above reference ellipsoid |
| Packet clock, both dates | UTC+00:00 fixed | UTC+10:00 fixed |
| Dates on the packet clock | 2026-06-21 and 2026-12-21 | 2026-06-21 and 2026-12-21 |
| Selected local sample times | 09:00, 11:00, 13:00, 15:00 | 09:00, 11:00, 13:00, 15:00 |

Greenwich is an explicitly author-selected educational reference near the public
observatory, not a surveyed position of the historic Airy telescope. The historic
and modern meridians are not identical: see [Royal Museums Greenwich](https://www.rmg.co.uk/stories/time/what-prime-meridian-why-it-greenwich).
Sydney follows the rounded coordinates published for [BOM station 066062](https://www.bom.gov.au/climate/averages/tables/cw_066062_SiteMap.shtml).
That source lists an actual elevation of 39 m. The model's height zero is a
deliberate simplification, not a claim that the station is at zero elevation.

The [JPL manual](https://ssd.jpl.nasa.gov/horizons/manual.html) specifies geodetic
coordinates in the Earth's reference frame. The captured output labels that
frame ITRF93. Height zero is relative to the reference ellipsoid, **not sea level,
terrain, a rooftop or eye height**. Neither reference includes hills, buildings,
trees or horizon dip. These are reproducible public mathematical viewpoints.

Packet clocks deliberately do not use daylight-saving rules. They must not be
presented as a visitor's legal local clock on those dates. JPL returns UT-labeled
epochs, which its documentation treats as UTC for these modern dates. The code
preserves UTC and converts with a fixed offset. In Sydney, 09:00 on June 21 is
23:00 UTC on June 20; sunrise 07:00 on June 21 is 21:00 UTC on June 20. Copying the
local date into a UTC field would be wrong. Each Sydney source day runs from
14:00 UTC on the preceding date to 14:00 UTC on the named date.

## Position source and precision

The [Horizons API documentation](https://ssd-api.jpl.nasa.gov/doc/horizons.html)
defines the recorded queries. They request Sun `10`, observer ephemerides,
Earth-centered geodetic surface coordinates, quantity `4`, Gregorian dates,
airless apparent positions, no daylight/elevation filtering, and CSV output
inside the JSON result. Returned headers identify Sun/Earth **DE441**, ITRF93,
API **1.2**, and EOP file `eop.261125.p270221`.

The source labels Earth-orientation inputs as data-based through 25 November
2026 and predictive after that date. December 21 was in the future when captured.
June is a retrospective calculation. Both are **calculated ephemerides**, not
eyewitness or instrument-recorded observations of the Sun.

JPL quantity 4 azimuth increases clockwise from true north: north 0, east 90,
south 180, west 270 degrees. It refers to the target's direction projected onto
the horizon and is separate from elevation. The selected source values describe
the Sun's center. Apparent airless coordinates incorporate JPL's documented
astronomical corrections but exclude atmospheric refraction. Six source decimal
places are retained for reproducibility, not asserted observational accuracy.

## Deriving the event labels

[USNO's rise/set definitions](https://aa.usno.navy.mil/faq/RST_defs) use the solar
center about 50 arcminutes below the geometric horizon: an average 16-arcminute
solar radius plus 34-arcminute near-horizon refraction convention. This packet
uses the exact rational threshold **-50/60 = -5/6 degree** on the saved airless
apparent solar-center elevation. Applying a threshold ourselves is an authored
calculation; the resulting event labels are **not a native JPL sunrise/set field**.

For each day the extractor requires all 1,441 minute timestamps including the
next midnight boundary. It detects one rising and one setting threshold bracket,
each one minute wide. Separate actual provider queries at each bracket's exact
half minute establish which endpoint is nearer the crossing. No fitted
subminute event time or interpolation is used. Exact half-minute ties choose the
later minute. The calculation assumes a continuous monotone crossing inside each
bracket; the endpoint and midpoint ordering is checked, not promoted into a
formal proof of continuous solar dynamics.

The learner interval is **sunset display minus sunrise display**. It is exact
arithmetic on rounded model times, not exact physical daylight. Endpoint rounding
alone can introduce up to one minute of interval difference; atmospheric and
geographic model limits are separate. Do not include civil twilight in the
sunrise-to-sunset interval. USNO explains that actual observed events can differ
by a minute or more because of atmospheric conditions, local topography and
observer height. Neither this derivation nor another service can validate what
was visible at these sites on the dates without observational evidence.

| Reference/date | Derived sunrise | Derived sunset | Displayed interval |
| --- | --- | --- | --- |
| Greenwich 2026-06-21 | 03:43 | 20:21 | 998 min = 16 h 38 min |
| Greenwich 2026-12-21 | 08:03 | 15:53 | 470 min = 7 h 50 min |
| Sydney 2026-06-21 | 07:00 | 16:54 | 594 min = 9 h 54 min |
| Sydney 2026-12-21 | 04:41 | 19:05 | 864 min = 14 h 24 min |

These are June/December comparison dates, not a claim that each is the exact
local date or instant of a solstice. Two sampled dates do not establish a yearly
maximum, minimum, complete seasonal curve or physical cause. The selected
reference points do not establish a rule for every place in a hemisphere.

## Direction rounding and missing states

Apply nearest-multiple-of-15 rounding **once to the complete source decimal**.
Halfway cases go clockwise to the next mark, followed by modulo 360: 7.5 becomes
15; 352.5 becomes 0; 360 is 0. There are 24 distinct direction cells, numbered
0-23, with cell 24 repeating north. Use decimal arithmetic, not Python's default
banker's rounding or a preliminary rounded decimal. Each rounded position differs
from its input by at most 7.5 degrees circularly. A difference between two rounded
positions is not an exact angular speed.

For example, Greenwich June 09:00 is 111.371720 degrees, shown as 105; 13:00 is
207.264056, shown as 210. Sydney June 11:00 is 15.264261, shown as 15; 13:00 is
343.123321, shown as 345. The latter pair has a 30-degree shorter anticlockwise
endpoint turn and a 330-degree clockwise marker turn. Neither proves an
unsampled continuous path.

| State | Treatment |
| --- | --- |
| Complete calculated sample above model horizon | Preserve raw source decimals; expose rounded direction |
| Provider value unavailable | Keep unknown with `source_missing`; never fill with zero, interpolate or label it a teaching omission |
| Center at/below model horizon | Keep technical provenance, exclude a numerical learner direction with `below_horizon` |
| Author deliberately removes a valid sample | Use `author_withheld_for_practice`; learner projection removes raw bearing, elevation, tick and cell |
| Rise/set absent, incomplete or not uniquely bracketed | Unknown/unusable for this packet, not zero duration and not automatic polar-day/night classification |

All sixteen selected source samples are above the airless model horizon. The
learner copy deliberately hides Greenwich December 11:00. A separate M1 card
hides the December Greenwich sunset. M1 is explicitly a restricted copy: the
complete original is available elsewhere, and C6 asks what M1 alone establishes.
These controls are rehearsal, not secure unseen assessment. Genuine source gaps
are not disguised as the authored omissions. A missing required source sample
stops complete answer-set generation.

## Limited USNO corroboration

The [USNO Greenwich annual table](https://aa.usno.navy.mil/calculated/rstt/year?ID=AA&label=Greenwich&lat=51.4769&lon=0.0000&task=0&tz=0&tz_sign=1&year=2026)
was successfully retrieved through normalized web output. A small factual row
was transcribed into the [disclosed excerpt](data/usno-greenwich-selected-excerpt.json).
This is not a raw HTTP capture. Subsequent direct/API/refetch attempts failed;
no usable USNO Sydney or azimuth output was obtained. We retain that limitation.

The table shows June 21 03:43-20:21 and December 21 08:03-15:53. All four labels
match the JPL-derived displayed labels. The [comparison record](data/source-comparison.json)
uses a one-minute event tolerance. USNO labels its table Universal Time and its
[API documentation](https://aa.usno.navy.mil/data/api.html) defines timezone
offsets relative to UT1. We do not assert UT1 and UTC are identical at subminute
precision. The requested latitude 51.4769 degrees is printed as N51 degrees
29 minutes in its header; internal coordinate rounding was not established.

This is independent-provider corroboration of selected Greenwich event labels.
It is not a second-provider check of every bearing or Sydney interval, and two
providers may share underlying astronomical models. Agreement is not independent
experimental evidence or observation validation.

## Reuse, access and review

[JPL SSD's FAQ](https://ssd.jpl.nasa.gov/faq.html) permits reuse of its data as
public-domain material, requests credit/source/date and clear identification of
modifications, and does not confer endorsement. Those credits appear in the
learner records. Only numeric USNO facts are excerpted with attribution; no
third-party explanatory prose, map, screenshot or exercise is redistributed.
The BOM page is referenced for its factual public coordinates, not copied.

The [JPL API policy](https://ssd-api.jpl.nasa.gov/doc/index.php) requires sequential
access, caching, an identifying application User-Agent and appropriate handling
of errors and rate limits. The explicit refresh CLI uses a project contact URL,
bounded exponential backoff, version checks and a fresh output directory. The
frozen packet and print materials work offline; no live API is embedded.

Available checks verify recorded source consistency, extraction, numerical
answers and omission controls. Independent human scientific review, age and
reading suitability, decimal-rounding scaffolds, access equivalence, accepted
time budget, fresh assessment forms and source/resource admission remain open.
No direct Sun viewing is permitted. No observed learner performance or teaching
readiness is claimed.
