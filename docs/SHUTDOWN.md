# Shutdown and data destruction protocol

Projects like this usually end. This page says what happens when this one does, so that a
contributor knows the answer before submitting rather than after.

## Kill criterion

Written before launch, so it is cheap to mean it:

> If, in the 30 days following a launch endorsed by at least one community moderator, fewer than
> 50 reports are received, the project will stop accepting submissions and enter shutdown.

Other triggers: the operator becomes unable or unwilling to maintain the site; a legal or
regulatory change makes continued operation impossible or unsafe for contributors; the legal
entity is dissolved.

## What happens on shutdown

In this order:

1. **Submissions close.** The form is removed. The site displays a notice with the date.
2. **A final release is published**, following the release specification, including the final
   Merkle root and integrity log. It is witnessed like every other release.
3. **The submission store is destroyed.** The SQLite file is securely deleted; every backup is
   deleted; the encryption keys for the backups are destroyed. This is done within 30 days of
   the closure notice. The date of destruction is published.
4. **The public artifacts remain.** The source code, the schema, the release specification, the
   threat model, and every published release stay online for as long as the domain and
   repository are maintained, and are mirrored to at least one archive we do not control.
5. **The domain is not sold.** It either continues to serve the archived site or lapses.

## What is never done

- The submission store is never transferred to any other party, for any consideration, under
  any circumstance — not on sale, not on merger, not on dissolution, not in bankruptcy. This is
  an irrevocable commitment in the site's terms.
- No "successor" project inherits the rows. A successor may inherit the code, the schema, and
  the methodology, and must collect its own data under its own commitments.
- No row-level export is ever made, including to a researcher, an archive, or a regulator, as
  part of shutdown.

The reason this can be promised is that the store does not contain anything that would be worth
transferring. Because no row identifies anyone, the dataset's value is entirely in the published
aggregates, which are already public. A trustee, an acquirer, or a court would find nothing in
the store that is not already in the releases, and nothing that could be used to find a person.

The 23andMe database was sold in bankruptcy to a nonprofit controlled by its own founder. An
organizational form is not a data covenant. This protocol is written so that the covenant does
not depend on the form.

## Succession

If the operator is incapacitated, the following happens automatically:

- The site continues to serve; no new submissions are affected because none are stored until
  confirm, and the store is not touched by any scheduled process.
- A designated person holds instructions and credentials sufficient to execute steps 1–5 above,
  and nothing more. They cannot read the store in any way the operator could not.

*Last updated: [date].*
