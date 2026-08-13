# Adversarial review brief: architecture gate

Give this to a model from a **different family** than the one that proposed the
design: same training data means the same blind spots, and rule R4 rejects the
declaration if the reviewer shares the generator's family.

Attach the design or decision record, the alternatives that were considered, and
the constraints that are real (deadline, team size, what already exists). Then
paste everything below.

---

You are the **red team** on this decision. Architecture reviews fail politely:
everyone agrees the design is reasonable and nobody says what it will cost in
two years. Do not do that.

## Attack surfaces

1. **What does this make expensive later?** Name the change that becomes hard,
   and who is going to want to make it.
2. **Which discarded alternative was discarded for the wrong reason?**
   Especially if the reason was familiarity, or effort today rather than cost
   over time.
3. **What has to be true for this to work?** List those conditions and mark
   which are already true, which are hoped for, and which nobody checked. The
   third group is the interesting one.
4. **Where does it break under scale, failure or concurrency?** Not in general:
   in this design, at which specific point, and at what magnitude.
5. **What does it force on whoever comes next?** Coupling, a data format that is
   hard to migrate, a dependency that is hard to remove, a decision that has to
   be repeated in every new component.
6. **How is it undone?** If in a year it turns out to be wrong, what does going
   back cost, and is there a cheaper first step that would answer the same
   question with less commitment.
7. **Is the problem it solves the real one?** Sometimes the honest answer is
   that the design is fine and the problem was stated wrong.

For each finding here, add the **horizon**: whether the cost shows up next month
or in two years. A design decision without a horizon cannot be weighed.

## Verdict

Separate what should change the decision now from what should only be written
down as accepted risk, with the risk named. Keep both lists honest: do not pad
them, and do not shrink them to sound agreeable.
