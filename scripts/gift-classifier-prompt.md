# Participant v6 gift classifier

Classify every `gift` event in the supplied Agent World `run.jsonl`, in
zero-based ledger order. Return exactly one classification for every gift and
do not classify accepted trades or construction contributions.

Use only these verdicts:

- `payment_for_service`: the gift is explicit consideration for a service or
  non-goods benefit, such as shelter access, upkeep, hauling, construction
  labor, or another performed obligation. Scoring credits service income to
  the recipient/vendor.
- `barter_settlement`: the gift explicitly settles one leg of a goods-for-goods
  exchange or a documented goods debt.
- `unrequited_transfer`: the ledger describes the transfer as aid, free, a
  gift, or otherwise provides evidence that no consideration was owed.
- `unclassifiable`: consideration is plausible but the ledger does not contain
  enough explicit evidence to establish it.

For `payment_for_service` and `barter_settlement`, `evidence_quote` must be a
verbatim substring of one ledger event's `message` field that explicitly
states the consideration. Proximity, reciprocal behavior, later gratitude,
or your inference is not enough. For `unrequited_transfer` and
`unclassifiable`, use an empty evidence quote. Keep reasoning concise and
state what establishes or fails to establish consideration.

Copy each gift's tick, giver, and recipient exactly from its event. Represent
the gift's `items` object as `item_entries`, with one entry per property using
the exact resource name and quantity; do not add or omit resources. Return only
the JSON object required by the output schema.
