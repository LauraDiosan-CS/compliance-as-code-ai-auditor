"""Daily quarantine digest e-mail sent to each employee."""

DIGEST_TEMPLATE = """Subject: Your quarantined messages ({count})

The following messages addressed to you were held by SpamShield, ACME's automated filter, which uses
a machine-learning model to classify incoming e-mail. Nothing has been deleted. If a message is not
spam, click "Release" and it will be delivered; your feedback is used to improve the filter.

{rows}

Quarantined messages are removed automatically after 30 days.
"""


def render(count: int, rows: list[str]) -> str:
    return DIGEST_TEMPLATE.format(count=count, rows="\n".join(rows))
