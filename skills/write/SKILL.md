---
name: write
description: Compose outbound prose that sounds human. Covers Slack messages, emails, GitHub issues and PR descriptions, LinkedIn posts, exec updates, customer replies. Picks the right register for the audience and strips AI tells before the draft is shown. Use when drafting, writing, or replying to any message a person will read; when the user says draft, write, reply, send, post, message, email, DM, follow up, announce, or share; and before pasting agent output into Slack, email, or a comment box.
---

# Write

Anything a human will read. The draft is the deliverable, not a summary of the draft.

## 0. Load the samples

Read `VOICE.md` before drafting anything that posts under Austen's name **unattributed** (GitHub comments, email, DMs). This file is rules; that file is real samples of him. Rules stop you sounding like slop. Samples make you sound like him. (`VOICE.md` is local-only and gitignored — it quotes internal threads verbatim.)

Skip it only for content he'll attribute or obviously rewrite himself.

## 1. Pick the register first

Austen's default voice (terse, opinionated, `idk` is allowed) is his **internal** voice. It is wrong in a customer email. Same person, different register.

| Channel | Length | Formality | Hedging | Emoji | Opener / closer |
|---|---|---|---|---|---|
| Internal Slack | 1–3 lines | low | fine | yes, incl. custom | none, just say it |
| Slack Connect (customer) | 2–5 lines | low-ish | fine | yes, standard | none, still Slack |
| Customer email | 3–8 lines | medium | minimal | no | "Hi <name>," / "Thanks, Austen" |
| Exec / leadership | 3–6 lines | medium | none | no | ask or conclusion first |
| GitHub issue / PR | as needed | low | fine | light | context → ask → owner |
| LinkedIn / public | short paras | medium | none | sparse | hook first, no CTA beg |

Unsure who the audience is? Ask. Guessing the register wrong is worse than one clarifying question.

## 2. Structure

Open with the finding, the conclusion, or the ask. One of those three, in the first sentence. Never build up to it.

Leading with the finding is correct even when the ask lands at the end. Do not front-load a meeting request ahead of the reason for it, that reads as cold outreach.

Then, only if it changes what the reader does: the why, the next action, the deadline and owner.

Cut any sentence that does not change a decision, an action, or a belief. If the draft is over five lines, cut it again unless length was requested.

Never use headers in a message under ~10 lines. Never bullet things that are sentences.

## 3. Kill list

Delete on sight, in every register:

**Punctuation**: em dashes. Use a period, comma, or parens.

**Hype**: seamless, robust, powerful, cutting-edge, game-changing, unlock, empower, elevate, supercharge, delve, realm, landscape, tapestry, testament to.

**Openers**: "I hope this finds you well", "In today's fast-paced world", "Great question!", "Certainly!", "I'd be happy to", "Let me start by".

**Closers**: "Let me know if you have any questions!", "Feel free to reach out", "Hope this helps!", "Happy to help!"

**Constructions**: "It's not just X, it's Y", "It's worth noting that", "It's important to note", "That said," as filler, rule-of-three lists that pad ("fast, reliable, and scalable").

**False framing**: "our records show", "it appears that", "I believe" when the fact is confirmed. State it.

**Filler intensifiers**: really, very, quite, incredibly, truly, simply.

**Nominalizations**: "provide clarification on" → "clarify". "Make a decision" → "decide".

Fix by rewriting the sentence, not by swapping the banned word for a synonym.

## 4. Specifics beat adjectives

"Usage dropped" is worthless. "GHR minutes dropped 40% since June 12" is a message. Pull the actual number, date, name, or link. If you do not have it, say you do not have it. Never pad with a qualitative stand-in.

Link everything that has a URL. Markdown links, never bare "click here".

## 5. Format handoff

Slack output: convert to mrkdwn. Bold is `*single asterisk*`, italic is `_underscore_`, no tables, flat lists. If a `slack-format` skill is available, use it for the full ruleset and the render-and-paste link method.

Email: plain prose. No markdown syntax, no bullets unless there is a genuine list.

GitHub: normal markdown, relative links for in-repo paths.

## 6. Adversarial review

A second pass by an agent that cannot see why you wrote it. Context is what let the bad sentence survive, so the reviewer gets the draft and the audience, nothing else.

**Run it automatically for:** customer email, Slack Connect, exec or leadership, LinkedIn or anything public, and any draft over ~10 lines.

**Skip it for:** internal Slack, GitHub comments, quick replies. The round trip costs more than the message is worth.

**Always run it when asked** to review, tighten, tear apart, or sanity-check a draft.

Launch a `task` subagent (`rubber-duck`) using the prompt template in [REVIEW.md](REVIEW.md). It returns a verdict, up to three blocking issues, and a ready-to-send rewrite.

Honor a `ship` verdict. If the reviewer clears the draft, send the original unchanged. Polishing past a clean review is how you reintroduce the slop.

## 7. Capture the rewrite

If Austen edits your draft before sending, **append the pair to the "Before/after pairs" section of `VOICE.md` before the session ends.** Your draft, his version, one-line lesson. Verbatim on both sides.

This is the only training signal the system gets, and it evaporates if you don't write it down. It also matters most for email and GitHub comments, where VOICE.md currently has zero real samples.

## Before you output

- [ ] Register matches the audience
- [ ] Finding, conclusion, or ask is in the first sentence
- [ ] Zero kill-list hits
- [ ] Every claim has a number, name, date, or link
- [ ] Would Austen actually send this, verbatim?
