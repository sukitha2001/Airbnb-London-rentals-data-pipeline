{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set schema_map = {
        'silver': 'airbnb_silver',
        'gold':   'airbnb_gold'
    } -%}

    {%- if custom_schema_name is none -%}
        {{ target.dataset }}
    {%- elif custom_schema_name in schema_map -%}
        {{ schema_map[custom_schema_name] }}
    {%- else -%}
        {{ target.dataset }}_{{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
