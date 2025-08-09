Install as custom component.
Retrieve warnings from https://www.met.ie/Open_Data/json/warning_IRELAND.json.
Creates three sensors, naes are depending on the areas choosen, all_ireland or counties:
1. sensor.met_eireann_active_warnings_count_NAME
   state - how many warnings
3. sensor.met_eireann_active_warnings_NAME
   state: active warnings
   attributes: warnings details
5. sensor.met_eireann_highest_warning_level_NAME
   state: higher warning alert colour (yelow, orange, red)
