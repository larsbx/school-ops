# Guided and exit teacher key — fully worked, draft

This is **teacher-only** answer guidance, not independent verification or the learner packet. Coordinates are `(column,row)`. For any shape `F`, `area(F)=|F|`; `perimeter(F)=4|F|-2·(number of unordered shared full sides)` in unit lengths. The perimeter argument holds for V/H/Q because these one-to-one moves preserve full-side adjacency and unit side length.

| Task | Exact answer and reasoning | Goal |
| --- | --- | --- |
| G1 | **(4,2)**; V pairs 1 and 4, and leaves row 2 unchanged. | P1 |
| G2 | **{(5,1),(4,1),(4,2),(4,3)}**; each of A's four cells has one distinct image, hence **4 square units**; not the original location. | P1/P3 |
| G3 | `(0,4)→(5,4)→(0,4)`; V is its own inverse, since `5-(5-c)=c`. | P1 |
| G4 | V(B) = **{(4,2),(3,2),(2,2),(1,2)}**, equal as a **set** to B; no individual B cell in these columns stays fixed, because the axis lies between cells. | P1/P3 |
| G5 | Q`(1,4)`=**(1,1)**; new column `5-4=1`, new row is the old column 1. | P2 |
| G6 | Q(A)=**{(4,0),(4,1),(3,1),(2,1)}**. V(A) has row indices 1,2,3, while Q(A) includes row 0, so not equal. | P2 |
| G7 | A has **4 square units**, **3 shared sides**, hence **16−6=10 length units**; Q(A) also has **4 square units** and **10 length units**. Q is a bijection of cells preserving neighbors; hence all exposed edges correspond. | P3/P4 |
| G8 | A: **4 square units, 10 length units**; D 2×2: **4 square units, 8 length units** (4 shared sides). Thus equal area does **not** determine perimeter. Reflection conservation speaks about **the same shape under an isometry**, not arbitrary shapes of equal area. | P3/P4 |

## Independent episode exit keys

| Exit | Required response and evidence |
| --- | --- |
| X1 | V`(0,3)`=**(5,3)**: columns 0 and 5 are equally far from the central vertical boundary; row stays 3. |
| X2 | `(2,2)→(3,2)→(2,2)`; **yes**, B as a set is V-symmetric because each bar cell swaps with another included bar cell; no individual B cell is fixed. |
| X3 | Q`(2,4)`=**(1,2)**, V`(2,4)`=**(3,4)**; a clockwise turn moves both coordinate roles while this vertical mirror changes only the column. |
| X4 | D **8 length units** (2×2), E **10 length units** (1×4). Both have **4 square units**; equal area alone does not force equal perimeter. |

**Progression:** Evaluate P1/P2 independently of P3/P4; no overall percentage may mask a missing ability to construct a mirror/turn or justify an invariant. If a learner gives only an answer number, ask for a reproducible coordinate or edge explanation. Read-aloud, tactile materials and response modes remain available, but teacher prompting that supplies a correct coordinate is not independent evidence. Use a fresh unseen teacher-approved form for any mastery judgment.
