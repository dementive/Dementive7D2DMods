from jinja2 import Template

properties_template = Template(
    """xml
    {% if group_name_key != blank %}<property name="group_name_key" value="{{group_name_key}}">{% endif %}
    {% if name_key != blank %}<property name="name_key" value="{{name_key}}">{% endif %}
    {% if subtitle_key != blank %}<property name="subtitle_key" value="{{subtitle_key}}">{% endif %}
    {% if description_key != blank %}<property name="description_key" value="{{description_key}}">{% endif %}
    {% if category_key != blank %}<property name="category_key" value="{{category_key}}">{% endif %}
    {% if offer_key != blank %}<property name="offer_key" value="{{offer_key}}">{% endif %}
    {% if statement_key != blank %}<property name="statement_key" value="{{statement_key}}">{% endif %}
    {% if response_key != blank %}<property name="response_key" value="{{response_key}}">{% endif %}
    {% if completion_key != blank %}<property name="completion_key" value="{{completion_key}}">{% endif %}
    {% if icon != blank %}<property name="icon" value="{{icon}}">{% endif %}
    {% if difficulty != blank %}<property name="difficulty" value="{{difficulty}}">{% endif %}
    {% if difficulty_tier != blank %}<property name="difficulty_tier" value="{{difficulty_tier}}">{% endif %}
    {% if login_rally_reset != blank %}<property name="login_rally_reset" value="{{login_rally_reset}}">{% endif %}
    {% if reward_choices_count != blank %}<property name="reward_choices_count" value="{{reward_choices_count}}">{% endif %}
    {% if extra_tags != blank %}<property name="extra_tags" value="{{extra_tags}}">{% endif %}
    {% if shareable != blank %}<property name="shareable" value="{{shareable}}">{% endif %}
    {% if repeatable != blank %}<property name="repeatable" value="{{repeatable}}">{% endif %}
    {% if completiontype != blank %}<property name="completiontype" value="{{completiontype}}">{% endif %}
    {% if spawn_multiplier != blank %}<property name="spawn_multiplier" value="{{spawn_multiplier}}">{% endif %}
    {% if gamestage_mod != blank %}<property name="gamestage_mod" value="{{gamestage_mod}}">{% endif %}
    {% if gamestage_bonus != blank %}<property name="gamestage_bonus" value="{{gamestage_bonus}}">{% endif %}
"""
)


def properties(
    group_name_key="",
    name_key="",
    subtitle_key="",
    description_key="",
    category_key="",
    offer_key="",
    statement_key="",
    response_key="",
    completion_key="",
    icon="",
    difficulty="",
    difficulty_tier="",
    login_rally_reset="",
    reward_choices_count="",
    extra_tags="",
    shareable="",
    repeatable="",
    completiontype="",
    spawn_multiplier="",
    gamestage_mod="",
    gamestage_bonus="",
):
    properties = properties_template.render(
        group_name_key=group_name_key,
        name_key=name_key,
        subtitle_key=subtitle_key,
        description_key=description_key,
        category_key=category_key,
        offer_key=offer_key,
        statement_key=statement_key,
        response_key=response_key,
        completion_key=completion_key,
        icon=icon,
        difficulty=difficulty,
        difficulty_tier=difficulty_tier,
        login_rally_reset=login_rally_reset,
        reward_choices_count=reward_choices_count,
        extra_tags=extra_tags,
        shareable=shareable,
        repeatable=repeatable,
        completiontype=completiontype,
        spawn_multiplier=spawn_multiplier,
        gamestage_mod=gamestage_mod,
        gamestage_bonus=gamestage_bonus,
    )[4:]
    return properties
