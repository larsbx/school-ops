# Khan Academy mathematics workflow

Use the connected Khan Academy capability to find assignable K–12 mathematics
questions. Curriculum structure, prerequisites, assessment criteria, and weekly
plans are maintained in this repository.

## Select practice for an outcome

1. Identify the course outcome and the mathematical topic needing practice.
2. Request questions on that topic in a dedicated Khan Academy interaction.
   Include a grade level or exact standard when you want that search limit.
3. Review the returned interactive questions for starting skills, difficulty,
   mathematical notation, and fit to the outcome.
4. Create a [resource record](../templates/resource.md) from the returned title,
   URL, and any reported standard. Record the query and review date, and distinguish
   intended course level from any provider-reported level.
5. Add the resource to the [register](../resources/README.md) and reference its
   ID from the lesson. Keep any class-specific assignment link in private planning.
6. Define the lesson's completion and assessment criteria. Assign the reviewed
   questions through the returned Khan Academy link when teaching that lesson.

Only use an explicit grade or standard supplied for the search. A course grade
range should not silently become a narrower exercise-search limit. Returned
metadata establishes what the provider reported; outcome alignment still requires
curriculum review.

The resource record may retain a general returned URL. If a link reveals a class,
learner, access token, or private assignment details, record its private location
instead of committing the link here.

## What is recorded

Record the resource title, provider, source URL where appropriate, query, outcome
IDs, reported standard, suitability review, and date. Leave unavailable metadata
as `not reported`; do not invent exercise IDs, links, or standards.

Store references to the selected material rather than copies of exercise content.
Exercise-selection replies follow the connected tool's interactive rendering;
repository updates happen in a separate curriculum-development interaction.

## Current integration boundary

The connected capability finds and displays assignable mathematics questions. It
does not provide a curriculum-wide course catalogue, non-math resource search,
learner-progress import, or automatic synchronization for this repository. No
questions have been selected or assigned as part of the foundation.
