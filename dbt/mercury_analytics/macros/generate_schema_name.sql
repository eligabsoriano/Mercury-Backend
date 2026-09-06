{# 
    Override dbt's default schema naming behavior.
    By default, dbt prepends the target schema (e.g., target_custom).
    This macro ensures that if a custom schema is specified (staging, intermediate, mart),
    it is used directly without prefixing.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
