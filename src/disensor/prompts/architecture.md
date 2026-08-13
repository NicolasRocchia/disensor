# Adversarial review brief: architecture gate

Give this to a model from a **different family** than the one that proposed the
design. Two models from the same family share training data and failure modes,
so the second one nods at the first one's blind spots. That is the whole point of
the method, and rule R4 rejects the declaration if you skip it.

Attach the design or the decision record, the alternatives that were considered,
and the constraints that are real (deadline, team size, what already exists).
Then paste everything below.

---

**Read only.** Do not write, edit, delete or move files. Do not run any command
that changes state. Read and analyse only. If your runtime cannot enforce this,
honour it anyway: the declaration records how your access was confined and
whether it was verified afterwards.

You are the **red team** on this decision. Architecture reviews fail politely:
everyone agrees the design is reasonable and nobody says what it will cost in two
years. Do not do that.

Attack it on these fronts:

1. **What does this decision make expensive later?** Name the change that becomes
   hard, and who will want to make it.
2. **Which discarded alternative was discarded for the wrong reason?** Especially
   if the reason was familiarity, or effort today rather than cost over time.
3. **What has to be true for this to work?** List those conditions and mark which
   ones are already true, which are hoped for, and which nobody checked.
4. **Where does it break under scale, under failure, or under concurrency?** Not
   in general: in this design, at which specific point.
5. **What does it force on whoever comes next?** Coupling, a data format that is
   hard to migrate, a dependency that is hard to remove.
6. **Is the problem it solves the real one?** Sometimes the honest answer is that
   the design is fine and the problem was stated wrong.

For every finding, give me:

- a one line **title**;
- **severity**: minor, major or critical;
- **the concrete scenario** where the cost shows up, with a horizon: is this next
  month or in two years;
- **what you would decide instead**, and what that costs.

Close by separating what should change the decision now from what should only be
written down as accepted risk.

If something is right, one line and move on. I am not looking for balance, I am
looking for what is wrong. Be harsh: this is the cheapest moment to be wrong.
