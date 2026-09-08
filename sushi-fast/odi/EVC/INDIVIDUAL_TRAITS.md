# Individual audience interest and knowledge

The web `topic_interest` and `prior_knowledge` settings remain low/middle/high
(0.25/0.50/0.75). They now specify population means, not identical traits for all six actors.

New sessions assign six distinct continuous values for each trait, within [0, 1].
Three balanced positive/negative pairs preserve each web mean without clipping bias.
The spread is at most 0.20, with independent seeded shuffles for interest and knowledge.
Assignments are persisted on `AudienceProfile.topic_interest` and `.prior_knowledge`,
and returned by session creation and restoration. They are fixed for a session;
they are not resampled on each update or tied to character gender.

Initial E = 2 × individual interest − 1; initial C = 2 × individual knowledge − 1.
V starts at zero. The former additional ±0.05 E/C noise is removed, so aggregate
initial E and C also match the transformed population means.

For negative changes, each actor uses sensitivity `1.4 − 0.8 × individual_trait`
(range 0.6–1.4). This extends the original anchors 0.25→1.2, 0.50→1.0, 0.75→0.8
continuously. Interest affects negative E; knowledge affects negative C.
Positive-change sensitivity and V remain 1.0, as in the existing state model.
State bounds remain [-1, 1]. This does not guarantee that all EVC states always
differ; identical evidence or saturation can legitimately produce equal values.

Old profiles without these fields load with None and retain the original group
setting sensitivity. Start a new session after server deployment to get individual
traits. Existing in-progress states are not silently rerandomized.

This change does not implement independent judgment clocks. That scheduling work
is separate from assigning and retaining personal state traits.

Validation covers all nine web-setting combinations across 100 seeds each,
six distinct bounded assignments, mean preservation, deterministic generation,
session restoration, individual negative-change sensitivity, and old-profile compatibility.
