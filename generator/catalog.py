"""The set of cron pages the site publishes.

Each entry targets one real search ("cron every 5 minutes", ...). `phrase`
is the human wording used in titles; `summary` is a one-sentence, hand-written
explanation. Everything else on a page is computed from `expr`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    slug: str
    expr: str
    phrase: str
    summary: str
    group: str


def _e(slug, expr, phrase, summary, group):
    return Entry(slug, expr, phrase, summary, group)


CATALOG = [
    # Minute intervals
    _e("every-minute", "* * * * *", "every minute",
       "Runs once a minute, every minute of every day.", "minutes"),
    _e("every-2-minutes", "*/2 * * * *", "every 2 minutes",
       "Runs on every even minute (:00, :02, :04 …) of every hour.", "minutes"),
    _e("every-5-minutes", "*/5 * * * *", "every 5 minutes",
       "Runs at :00, :05, :10 … :55 of every hour, every day.", "minutes"),
    _e("every-10-minutes", "*/10 * * * *", "every 10 minutes",
       "Runs six times an hour, at :00, :10, :20, :30, :40 and :50.", "minutes"),
    _e("every-15-minutes", "*/15 * * * *", "every 15 minutes",
       "Runs four times an hour, at :00, :15, :30 and :45.", "minutes"),
    _e("every-20-minutes", "*/20 * * * *", "every 20 minutes",
       "Runs three times an hour, at :00, :20 and :40.", "minutes"),
    _e("every-30-minutes", "*/30 * * * *", "every 30 minutes",
       "Runs twice an hour, on the hour and at half past.", "minutes"),
    _e("every-45-minutes", "*/45 * * * *", "every 45 minutes",
       "A common mistake: this runs at :00 and :45 of each hour, not every 45 minutes.", "minutes"),
    _e("every-7-minutes", "*/7 * * * *", "every 7 minutes",
       "Runs at every multiple of 7 past the hour, so the gap resets each hour.", "minutes"),
    # Hour intervals
    _e("every-hour", "0 * * * *", "every hour",
       "Runs once an hour, exactly on the hour.", "hours"),
    _e("every-2-hours", "0 */2 * * *", "every 2 hours",
       "Runs on the hour at every even hour: 00:00, 02:00, 04:00 … 22:00.", "hours"),
    _e("every-3-hours", "0 */3 * * *", "every 3 hours",
       "Runs eight times a day: 00:00, 03:00, 06:00 … 21:00.", "hours"),
    _e("every-4-hours", "0 */4 * * *", "every 4 hours",
       "Runs six times a day: 00:00, 04:00, 08:00, 12:00, 16:00 and 20:00.", "hours"),
    _e("every-6-hours", "0 */6 * * *", "every 6 hours",
       "Runs four times a day: 00:00, 06:00, 12:00 and 18:00.", "hours"),
    _e("every-12-hours", "0 */12 * * *", "every 12 hours",
       "Runs twice a day, at midnight and noon.", "hours"),
    _e("every-5-hours", "0 */5 * * *", "every 5 hours",
       "Runs at 00:00, 05:00, 10:00, 15:00 and 20:00, then resets at midnight.", "hours"),
    _e("every-hour-at-30", "30 * * * *", "every hour at half past",
       "Runs once an hour, at 30 minutes past.", "hours"),
    # Daily
    _e("every-day-at-midnight", "0 0 * * *", "every day at midnight",
       "Runs once a day at 00:00.", "daily"),
    _e("every-day-at-1am", "0 1 * * *", "every day at 1am",
       "Runs once a day at 01:00.", "daily"),
    _e("every-day-at-2am", "0 2 * * *", "every day at 2am",
       "Runs once a day at 02:00, a popular slot for backups.", "daily"),
    _e("every-day-at-6am", "0 6 * * *", "every day at 6am",
       "Runs once a day at 06:00.", "daily"),
    _e("every-day-at-8am", "0 8 * * *", "every day at 8am",
       "Runs once a day at 08:00.", "daily"),
    _e("every-day-at-9am", "0 9 * * *", "every day at 9am",
       "Runs once a day at 09:00.", "daily"),
    _e("every-day-at-noon", "0 12 * * *", "every day at noon",
       "Runs once a day at 12:00.", "daily"),
    _e("every-day-at-6pm", "0 18 * * *", "every day at 6pm",
       "Runs once a day at 18:00.", "daily"),
    _e("twice-a-day", "0 0,12 * * *", "twice a day",
       "Runs at midnight and at noon.", "daily"),
    _e("every-day-at-8am-and-8pm", "0 8,20 * * *", "every day at 8am and 8pm",
       "Runs twice a day, at 08:00 and 20:00.", "daily"),
    # Weekly / weekdays
    _e("every-weekday", "0 0 * * 1-5", "every weekday",
       "Runs at midnight Monday through Friday.", "weekly"),
    _e("every-weekday-at-9am", "0 9 * * 1-5", "every weekday at 9am",
       "Runs at 09:00 Monday through Friday, never on weekends.", "weekly"),
    _e("every-weekend", "0 0 * * 0,6", "every weekend",
       "Runs at midnight on Saturday and on Sunday.", "weekly"),
    _e("every-monday", "0 0 * * 1", "every Monday",
       "Runs once a week, at midnight at the start of Monday.", "weekly"),
    _e("every-monday-at-9am", "0 9 * * 1", "every Monday at 9am",
       "Runs once a week, Monday at 09:00.", "weekly"),
    _e("every-friday-at-5pm", "0 17 * * 5", "every Friday at 5pm",
       "Runs once a week, Friday at 17:00.", "weekly"),
    _e("every-sunday", "0 0 * * 0", "every Sunday",
       "Runs once a week, at midnight at the start of Sunday.", "weekly"),
    _e("every-sunday-at-3am", "0 3 * * 0", "every Sunday at 3am",
       "Runs once a week, Sunday at 03:00, a common maintenance window.", "weekly"),
    # Business hours
    _e("every-hour-business-hours", "0 9-17 * * 1-5", "every hour during business hours",
       "Runs on the hour from 09:00 to 17:00, Monday to Friday.", "business"),
    _e("every-15-minutes-business-hours", "*/15 9-17 * * 1-5", "every 15 minutes during business hours",
       "Runs every 15 minutes from 09:00 until 17:45, Monday to Friday.", "business"),
    _e("every-30-minutes-business-hours", "*/30 9-17 * * 1-5", "every 30 minutes during business hours",
       "Runs on the hour and half hour from 09:00 until 17:30, Monday to Friday.", "business"),
    # Monthly / yearly
    _e("every-month", "0 0 1 * *", "every month",
       "Runs once a month, at midnight on the 1st.", "monthly"),
    _e("first-and-fifteenth", "0 0 1,15 * *", "on the 1st and 15th of every month",
       "Runs twice a month, at midnight on the 1st and the 15th.", "monthly"),
    _e("every-month-on-the-15th", "0 0 15 * *", "on the 15th of every month",
       "Runs once a month, at midnight on the 15th.", "monthly"),
    _e("every-2-months", "0 0 1 */2 *", "every 2 months",
       "Runs at midnight on the 1st of January, March, May, July, September and November.", "monthly"),
    _e("every-quarter", "0 0 1 1,4,7,10 *", "every quarter",
       "Runs at midnight on the first day of each quarter: Jan 1, Apr 1, Jul 1 and Oct 1.", "monthly"),
    _e("every-6-months", "0 0 1 1,7 *", "every 6 months",
       "Runs twice a year, at midnight on January 1 and July 1.", "monthly"),
    _e("every-year", "0 0 1 1 *", "every year",
       "Runs once a year, at midnight on January 1.", "monthly"),
    _e("on-the-31st", "0 0 31 * *", "on the 31st of the month",
       "Runs only in months that have 31 days; it is not a “last day of month” schedule.", "monthly"),
]

GROUP_TITLES = {
    "minutes": "Every N minutes",
    "hours": "Every N hours",
    "daily": "Daily",
    "weekly": "Weekly and weekdays",
    "business": "Business hours",
    "monthly": "Monthly and yearly",
}

BY_SLUG = {e.slug: e for e in CATALOG}
assert len(BY_SLUG) == len(CATALOG), "duplicate slug"
