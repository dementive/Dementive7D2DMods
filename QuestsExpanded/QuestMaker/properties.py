from jinja2 import Template

properties_template = Template(
    """xml
    {% if group_name_key != "" %}<property name="group_name_key" value="{{group_name_key}}">{% endif %}
    {% if name_key != "" %}<property name="name_key" value="{{name_key}}">{% endif %}
    {% if subtitle_key != "" %}<property name="subtitle_key" value="{{subtitle_key}}">{% endif %}
    {% if description_key != "" %}<property name="description_key" value="{{description_key}}">{% endif %}
    {% if category_key != "" %}<property name="category_key" value="{{category_key}}">{% endif %}
    {% if offer_key != "" %}<property name="offer_key" value="{{offer_key}}">{% endif %}
    {% if statement_key != "" %}<property name="statement_key" value="{{statement_key}}">{% endif %}
    {% if response_key != "" %}<property name="response_key" value="{{response_key}}">{% endif %}
    {% if completion_key != "" %}<property name="completion_key" value="{{completion_key}}">{% endif %}
    {% if icon != "" %}<property name="icon" value="{{icon}}">{% endif %}
    {% if difficulty != "" %}<property name="difficulty" value="{{difficulty}}">{% endif %}
    {% if difficulty_tier != "" %}<property name="difficulty_tier" value="{{difficulty_tier}}">{% endif %}
    {% if login_rally_reset != "" %}<property name="login_rally_reset" value="{{login_rally_reset}}">{% endif %}
    {% if reward_choices_count != "" %}<property name="reward_choices_count" value="{{reward_choices_count}}">{% endif %}
    {% if shareable != "" %}<property name="shareable" value="{{shareable}}">{% endif %}
    {% if repeatable != "" %}<property name="repeatable" value="{{repeatable}}">{% endif %}
    {% if completiontype != "" %}<property name="completiontype" value="{{completiontype}}">{% endif %}
    {% if extra_tags != "" %}<property name="extra_tags" value="{{extra_tags}}">{% endif %}{% if spawn_multiplier != "" %}<property name="spawn_multiplier" value="{{spawn_multiplier}}">{% endif %}
    {% if gamestage_mod != "" %}<property name="gamestage_mod" value="{{gamestage_mod}}">{% endif %}{% if gamestage_bonus != "" %}<property name="gamestage_bonus" value="{{gamestage_bonus}}">{% endif %}""")

class Properties:

    def __init__(self):
        self.localization_keys = list()

    def write(self):
        with open("Localization.txt", "w") as file:
            file.write("Key,File,Type,UsedInMainMenu,NoTranslate,english,Context / Alternate ")
        with open("Localization.txt", "a") as file:
            for i in self.localization_keys:
                file.write("\n")
                for j in i:
                    file.write(j)
                    if any(substring in j for substring in ("_group", "_statement", "_response")):
                        file.write(",Quest,Quest Info,,,")
                    else:
                        file.write(",quests,Quests,,,")
                    file.write("\n")

    def properties(
        self,
        group_name_key="",
        name_key="",
        subtitle_key="",
        description_key="",
        category_key="",
        offer_key="",
        statement_key="",
        response_key="",
        completion_key="",
        icon="ui_game_symbol_quest",
        difficulty="medium",
        difficulty_tier="",
        login_rally_reset="true",
        reward_choices_count="5",
        extra_tags="",
        shareable="true",
        repeatable="true",
        completiontype="TurnIn",
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

        loc_keys = [group_name_key, name_key, subtitle_key, description_key, category_key, offer_key, statement_key, response_key, completion_key]
        self.localization_keys.append(loc_keys)

        return properties