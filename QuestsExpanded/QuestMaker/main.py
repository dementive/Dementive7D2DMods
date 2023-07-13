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
tier_1_pois = True

if urban:
    current_tier = 1
    quest_id = f"tier{current_tier}_urban_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_urban_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 2
    quest_id = f"tier{current_tier}_urban_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier2_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_urban_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier2_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 3
    quest_id = f"tier{current_tier}_urban_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_urban_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 4
    quest_id = f"tier{current_tier}_urban_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier4_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_urban_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="downtown, commercial, industrial" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier4_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

if rural:
    current_tier = 1
    quest_id = f"tier{current_tier}_rural_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_rural_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 2
    quest_id = f"tier{current_tier}_rural_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier2_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_rural_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier2_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 3
    quest_id = f"tier{current_tier}_rural_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_rural_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    current_tier = 4
    quest_id = f"tier{current_tier}_rural_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier4_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_rural_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="include_tags" value="countrytown, countryresidential, rural" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier4_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

if tier_1_pois:
    current_tier = 1

    # Cabins
    quest_id = f"tier{current_tier}_cabin_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="cabin_01,cabin_06,cabin_09,cabin_11,cabin_07,cabin_05,cabin_08,cabin_14,cabin_02,cabin_12,cabin_15,cabin_10,cabin_04,cabin_16" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_cabin_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="cabin_01,cabin_06,cabin_09,cabin_11,cabin_07,cabin_05,cabin_08,cabin_14,cabin_02,cabin_12,cabin_15,cabin_10,cabin_04,cabin_16" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Survivor Sites
    quest_id = f"tier{current_tier}_survivor_site_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="survivor_site_02,survivor_site_05,survivor_site_06,survivor_site_08,survivor_site_03,survivor_site_09,survivor_site_01,survivor_site_10,survivor_site_11,survivor_site_07" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_survivor_site_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="survivor_site_02,survivor_site_05,survivor_site_06,survivor_site_08,survivor_site_03,survivor_site_09,survivor_site_01,survivor_site_10,survivor_site_11,survivor_site_07" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Fast Food
    quest_id = f"tier{current_tier}_fast_food_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="fastfood_03,fastfood_02,fastfood_01,fastfood_05" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_fast_food_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="fastfood_03,fastfood_02,fastfood_01,fastfood_05" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Caves
    quest_id = f"tier{current_tier}_caves_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="cave_05,cave_01,cave_04,cave_03,cave_02" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_caves_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="cave_05,cave_01,cave_04,cave_03,cave_02" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Stores
    quest_id = f"tier{current_tier}_store_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="store_electronics_01,store_grocery_05,store_grocery_04,store_grocery_06,store_laundry_01,store_pharmacy_01" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_store_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="store_electronics_01,store_grocery_05,store_grocery_04,store_grocery_06,store_laundry_01,store_pharmacy_01" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Gas Station
    quest_id = f"tier{current_tier}_gas_station_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="gas_station_11,gas_station_04,gas_station_08,gas_station_10,gas_station_01,gas_station_09,fastfood_04,gas_station_03,gas_station_02,gas_station_07" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_gas_station_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="gas_station_11,gas_station_04,gas_station_08,gas_station_10,gas_station_01,gas_station_09,fastfood_04,gas_station_03,gas_station_02,gas_station_07" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Diner
    quest_id = f"tier{current_tier}_diner_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="diner_01,diner_02,diner_03,diner_04" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_diner_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="diner_01,diner_02,diner_03,diner_04" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Ranger Station
    quest_id = f"tier{current_tier}_ranger_station_clear"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="ranger_station_02,ranger_station_03,ranger_station_04,ranger_station_05" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_ranger_station_fetch"
    properties = property_object.properties(
        group_name_key=f"{quest_id}_group_name",
        name_key=f"{quest_id}_quest_name",
        subtitle_key=f"{quest_id}_subtitle",
        description_key=f"{quest_id}_description",
        category_key=f"{quest_id}_category",
        offer_key=f"{quest_id}_offer",
        statement_key=f"{quest_id}_statement",
        response_key=f"{quest_id}_response",
        completion_key=f"{quest_id}_completion",
        difficulty_tier=str(current_tier),
    )
    objectives = """xml
    <objective type="GotoPOISDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="ranger_station_02,ranger_station_03,ranger_station_04,ranger_station_05" />
    </objective>
    """[3:] + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))


quest_list.write()
property_object.write()