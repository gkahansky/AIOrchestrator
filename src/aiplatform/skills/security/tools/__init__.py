# Security scanning tool wrappers
# Each module wraps one binary tool and normalises its output into the
# standard finding dict consumed by the pipeline and Claude correlation.
#
# Normalised finding schema:
# {
#     "tool":         str,   # source tool name
#     "title":        str,
#     "severity":     str,   # critical / high / medium / low / info
#     "category":     str,
#     "description":  str,
#     "url":          str,   # matched URL
#     "evidence":     str,   # raw match / snippet / request line
#     "cvss_estimate": float,
#     "fix":          str,
#     "tags":         list[str],
# }
#
# All wrappers return [] gracefully when the binary is not installed.
