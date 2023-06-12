_ = [
    {
        "definitions": {
            "not a ref": {"$ref": 0},
            "also not ref": {"enum": [{"$ref": "#"}]},
            "actual ref": {"$ref": "#"},
            "ref deleted twice": {"enum": {"default": "$ref"}},
        }
    },
    {
        "not a ref": {"$ref": 0},
        "also not ref": {"enum": [{"$ref": "#"}]},
        "actual ref": {"$ref": "#"},
        "ref deleted twice": {"enum": {"default": "$ref"}},
    },
    {"$ref": 0},
    0,
    {"enum": [{"$ref": "#"}]},
    [{"$ref": "#"}],
    {"$ref": "#"},
    "#",
]
