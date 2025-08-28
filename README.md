Install as custom component.
Retrieve warnings from https://www.met.ie/Open_Data/json/warning_IRELAND.json.
Creates three sensors, names are depending on the areas choosen, all_ireland or counties:
1. sensor.met_eireann_active_warnings_count_NAME
   state - how many warnings
3. sensor.met_eireann_active_warnings_NAME
   state: active warnings
   attributes: warnings details
5. sensor.met_eireann_highest_warning_level_NAME
   state: higher warning alert colour (yelow, orange, red)


Warnings automation example:
```
alias: "Met Éireann Weather Warning Notifications"
description: "Send mobile notifications for active weather warnings"
trigger:
  - platform: state
    entity_id: sensor.met_eireann_active_warnings_ireland
    attribute: warnings
mode: queued
max: 10
condition:
  - condition: template
    value_template: >
      {{ trigger.to_state.attributes.active_warnings_count | int > 0 }}
action:
  - repeat:
      for_each: "{{ trigger.to_state.attributes.warnings }}"
      sequence:
        - variables:
            warning: "{{ repeat.item }}"
            level: "{{ warning.level | default('Unknown') }}"
            severity: "{{ warning.severity | default('Unknown') }}"
            headline: "{{ warning.headline | default('Weather Warning') }}"
            description: "{{ warning.description | default('No description available') | replace('&gt;', '>') | replace('&lt;', '<') | replace('&amp;', '&') }}"
            regions: "{{ warning.regions | join(', ') if warning.regions else 'Ireland' }}"
            issued: "{{ warning.issued | default('Unknown') }}"
            expires: "{{ warning.expires | default('Unknown') }}"
            warning_type: "{{ warning.type | default('Weather') }}"
        - service: notify.mobile_app_your_phone_name
          data:
            title: "{{ level }} warning for {{ regions }}"
            message: >
              **{{ headline }}**
              
              **Type:** {{ warning_type }}
              **Severity:** {{ severity }}
              **Issued:** {{ issued | as_timestamp | timestamp_custom('%d/%m/%Y %H:%M') if issued != 'Unknown' else 'Unknown' }}
              **Expires:** {{ expires | as_timestamp | timestamp_custom('%d/%m/%Y %H:%M') if expires != 'Unknown' else 'Unknown' }}
              
              **Description:**
              {{ description }}
            data:
              tag: "met_eireann_{{ warning.id }}"
              group: "weather_warnings"
              color: >
                {% if level | lower == 'red' %}
                  red
                {% elif level | lower == 'orange' %}
                  orange
                {% elif level | lower == 'yellow' %}
                  yellow
                {% else %}
                  blue
                {% endif %}
              importance: >
                {% if level | lower == 'red' %}
                  high
                {% elif level | lower == 'orange' %}
                  default
                {% else %}
                  low
                {% endif %}
              icon_url: >
                {% if level | lower == 'red' %}
                  https://cdn-icons-png.flaticon.com/512/564/564619.png
                {% elif level | lower == 'orange' %}
                  https://cdn-icons-png.flaticon.com/512/1163/1163661.png
                {% else %}
                  https://cdn-icons-png.flaticon.com/512/1163/1163662.png
                {% endif %}
              actions:
                - action: "view_details"
                  title: "View Details"
                - action: "dismiss_warning"
                  title: "Dismiss"
    ```
