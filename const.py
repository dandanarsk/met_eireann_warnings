"""Constants for the Met Éireann Weather Warnings integration."""

DOMAIN = "met_eireann_warnings"

WARNING_LEVELS = {
    "red": {
        "color": "#d32f2f",
        "priority": 3,
        "icon": "mdi:alert-octagon"
    },
    "orange": {
        "color": "#f57c00", 
        "priority": 2,
        "icon": "mdi:alert"
    },
    "yellow": {
        "color": "#fbc02d",
        "priority": 1,
        "icon": "mdi:alert-outline"
    }
}

# Area selection options
AREA_OPTIONS = {
    "whole_ireland": "Whole Ireland",
    "regions": "Select Regions",
    "counties": "Select Counties"
}

# Irish regions
REGIONS = {
    "connacht": "Connacht",
    "leinster": "Leinster", 
    "munster": "Munster",
    "ulster": "Ulster"
}

# Irish counties
COUNTIES = {
    # Connacht
    "galway": "Galway",
    "mayo": "Mayo",
    "roscommon": "Roscommon",
    "sligo": "Sligo",
    "leitrim": "Leitrim",
    
    # Leinster
    "dublin": "Dublin",
    "wicklow": "Wicklow",
    "wexford": "Wexford",
    "carlow": "Carlow",
    "kilkenny": "Kilkenny",
    "laois": "Laois",
    "longford": "Longford",
    "louth": "Louth",
    "meath": "Meath",
    "offaly": "Offaly",
    "westmeath": "Westmeath",
    "kildare": "Kildare",
    
    # Munster
    "cork": "Cork",
    "kerry": "Kerry",
    "limerick": "Limerick",
    "tipperary": "Tipperary",
    "waterford": "Waterford",
    "clare": "Clare",
    
    # Ulster (Republic of Ireland part)
    "cavan": "Cavan",
    "donegal": "Donegal",
    "monaghan": "Monaghan"
}

# Region to county mapping
REGION_TO_COUNTIES = {
    "connacht": ["galway", "mayo", "roscommon", "sligo", "leitrim"],
    "leinster": ["dublin", "wicklow", "wexford", "carlow", "kilkenny", "laois", 
                 "longford", "louth", "meath", "offaly", "westmeath", "kildare"],
    "munster": ["cork", "kerry", "limerick", "tipperary", "waterford", "clare"],
    "ulster": ["cavan", "donegal", "monaghan"]
}
