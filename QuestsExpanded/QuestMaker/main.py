from properties import Properties
from objectives import Objectives
from rewards import Rewards
from quest import QuestList, make_quest

"""
    This is a slightly nicer way to write quests for 7 days to die since the regular quests.xml isn't nearly as flexible as python
"""

quest_list = QuestList()
property_object = Properties()

urban = True
rural = True

# Set if generating infested quests
infested_quest = True
infested_string = "infested_" if infested_quest else ""

if urban:
    if infested_quest is False:
        current_tier = 1
        quest_id = f"tier{current_tier}_{infested_string}urban_clear"
        properties = property_object.properties(
            name_key=f"{quest_id}_quest_name",
            subtitle_key=f"{quest_id}_subtitle",
            description_key=f"{quest_id}_description",
            offer_key=f"{quest_id}_offer",
            statement_key=f"{quest_id}_statement",
            response_key=f"{quest_id}_response",
            completion_key=f"{quest_id}_completion",
            difficulty_tier=str(current_tier),
        )
        objectives = """
        <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
            <property name="phase" value="1" />
            <property name="nav_object" value="quest" />
            <property name="include_tags" value="downtown, commercial, industrial" />
        </objective>
        """ + Objectives().objective_clear_ending
        rewards = Rewards().tier1_clear_rewards
        quest_list.append(make_quest(quest_id, properties, objectives, rewards))

        quest_id = f"tier{current_tier}_{infested_string}urban_fetch"
        properties = property_object.properties(
            name_key=f"{quest_id}_quest_name",
            subtitle_key=f"{quest_id}_subtitle",
            description_key=f"{quest_id}_description",
            offer_key=f"{quest_id}_offer",
            statement_key=f"{quest_id}_statement",
            response_key=f"{quest_id}_response",
            completion_key=f"{quest_id}_completion",
            difficulty_tier=str(current_tier),
        )
        objectives = """
        <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
            <property name="phase" value="1" />
            <property name="nav_object" value="quest" />
            <property name="include_tags" value="downtown, commercial, industrial" />
        </objective>
        """ + Objectives().objective_fetch_ending
        rewards = Rewards().tier1_fetch_rewards
        quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 2
    quest_id = f"tier{current_tier}_{infested_string}urban_clear"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier2_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}urban_fetch"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier2_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 3
    quest_id = f"tier{current_tier}_{infested_string}urban_clear"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}urban_fetch"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 4
    quest_id = f"tier{current_tier}_{infested_string}urban_clear"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier4_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}urban_fetch"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier4_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

if rural:
    if infested_quest is False:
        current_tier = 1
        quest_id = f"tier{current_tier}_{infested_string}rural_clear"
        properties = property_object.properties(
            name_key=f"{quest_id}_quest_name",
            subtitle_key=f"{quest_id}_subtitle",
            description_key=f"{quest_id}_description",
            offer_key=f"{quest_id}_offer",
            statement_key=f"{quest_id}_statement",
            response_key=f"{quest_id}_response",
            completion_key=f"{quest_id}_completion",
            difficulty_tier=str(current_tier),
        )
        objectives = """
        <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
            <property name="phase" value="1" />
            <property name="nav_object" value="quest" />
            <property name="include_tags" value="countrytown, countryresidential, rural" />
        </objective>
        """ + Objectives().objective_clear_ending
        rewards = Rewards().tier1_clear_rewards
        quest_list.append(make_quest(quest_id, properties, objectives, rewards))

        quest_id = f"tier{current_tier}_{infested_string}rural_fetch"
        properties = property_object.properties(
            name_key=f"{quest_id}_quest_name",
            subtitle_key=f"{quest_id}_subtitle",
            description_key=f"{quest_id}_description",
            offer_key=f"{quest_id}_offer",
            statement_key=f"{quest_id}_statement",
            response_key=f"{quest_id}_response",
            completion_key=f"{quest_id}_completion",
            difficulty_tier=str(current_tier),
        )
        objectives = """
        <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
            <property name="phase" value="1" />
            <property name="nav_object" value="quest" />
            <property name="include_tags" value="countrytown, countryresidential, rural" />
        </objective>
        """ + Objectives().objective_fetch_ending
        rewards = Rewards().tier1_fetch_rewards
        quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 2
    quest_id = f"tier{current_tier}_{infested_string}rural_clear"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier2_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}rural_fetch"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier2_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 3
    quest_id = f"tier{current_tier}_{infested_string}rural_clear"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}rural_fetch"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 4
    quest_id = f"tier{current_tier}_{infested_string}rural_clear"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier4_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}rural_fetch"
    properties = property_object.properties(
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
        infested_quest=infested_quest,
    )
    objectives = """
    <objective type="RandomTaggedPOIGotoDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier4_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

quest_list.write()
property_object.write()