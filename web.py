import re

PHONE_RE = re.compile(
    r"""(
        (?:\+?\d{1,3}[\s\-\.])?          # optional country code
        (?:\(?\d{2,4}\)?[\s\-\.]?)?     # optional area code
        (?:\d{3,4}[\s\-\.]?\d{3,4})     # local number groups
    )""",
    re.VERBOSE,
)

WEBSITE_RE = re.compile(
    r"""(
        (?:https?://)?                  # optional scheme
        (?:www\.)?                      # optional www
        [a-zA-Z0-9\-\_]{1,63}           # domain name part
        (?:\.[a-zA-Z0-9\-\_]{1,63})+    # one or more dot-suffixes
        (?:[/:?&=#][^\s]*)?             # optional path/query/fragment
    )""",
    re.VERBOSE | re.IGNORECASE,
)
