# HEARTBEAT — Periodic Check Tasks

Every heartbeat (2h), do the following:

1. **Email scan**: `gog gmail search 'is:unread' --account YOUR_EMAIL@gmail.com --json`
   - Flag any recruiter responses, interview invites, or scheduling links as URGENT
   - Update job tracker with any status changes
   - If interview invite found, WhatsApp user IMMEDIATELY

2. **Queue health check**: Read `workspace/job-queue.md`
   - Count PENDING jobs — if < 5, note that Search Agent needs to find more
   - Check for any jobs stuck in IN PROGRESS for > 30 min
   - Verify queue is sorted correctly by priority score

3. **Follow-up check**: Review `workspace/job-tracker.md` for applications with no response after 5+ days
   - Draft follow-up emails for stale applications
   - Send via `gog gmail send`

4. **Pipeline health**: Count total active applications by stage in job-tracker.md
   - If pipeline is thin (< 20 active applications), flag as concern

5. **WhatsApp user** only if there's something actionable:
   - Interview invites or scheduling links (ALWAYS notify)
   - Daily pipeline summary (once per day, evening)
   - Recruiter responses requiring action
   - Don't spam with routine updates

## Deadline Countdown
<!-- CUSTOMIZE: Set your own deadline -->
Calculate days remaining until your job search deadline. Include in any summary.
