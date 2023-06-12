import re

schema_dict_keys = "|".join(["definitions", "properties", "patternProperties", "dependencies"])
schema_array_keys = "|".join(["items", "allOf", "anyOf", "oneOf"])
schema_keys = "|".join(["additionalItems", "items", "additionalProperties", "not"])

string_pattern = rf"""
(?:
    ^    # anchored
    (?:
            (?:
                \/(?:{schema_keys}) |              #  captures all direct schema locations, like /not
                \/(?:{schema_array_keys})\/[0-9]+ |#  captures all schemas in a array (should still check if it is a dict though)
                \/(?:{schema_dict_keys})\/[^\/]+   #  caputures all schemas in a dict key
            )+   # allowed to repeat itself multiple times, at least once
    | \/+ # alternate patterns for top level '' is valid, so is '/'
    )
    $    # anchored
    | ^$
)"""


valid_schema_pointers: re.Pattern = re.compile(string_pattern, re.VERBOSE)




