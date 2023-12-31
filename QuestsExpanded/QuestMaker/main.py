from properties import Properties
from objectives import Objectives
from rewards import Rewards
from quest import QuestList, make_quest
from zztong_pois import ZZTongPois

"""
    This is a slightly nicer way to write quests for 7 days to die since the regular quests.xml isn't nearly as flexible as python
"""

quest_list = QuestList()
property_object = Properties()

urban = True
rural = True
tier_1_pois = True
tier_2_pois = True
tier_3_pois = True
tier_4_pois = True
tier_5_pois = True

# Set if generating infested quests
infested_quest = True
infested_string = "infested_" if infested_quest else ""

# Set if generating quests that include ZZtong prefabs
ZPois = ZZTongPois()
ZPois.make_quests()

zztong_t1_caves = ZPois.t1_caves
zztong_t1_cabins = ZPois.t1_cabins
zztong_t1_stations = ZPois.t1_stations
zztong_t1_stores = ZPois.t1_stores

zztong_t2_farm = ZPois.t2_farm
zztong_t2_store = ZPois.t2_store

zztong_t3_farm = ZPois.t3_farm
zztong_t3_store = ZPois.t3_store

zztong_t4_army = ZPois.t4_army
zztong_t4_downtown = ZPois.t4_downtown
zztong_t4_store = ZPois.t4_store

zztong_t5_skyscraper = ZPois.t5_skyscraper

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

if tier_1_pois and infested_quest is False:
    current_tier = 1

    # Cabins
    quest_id = f"tier{current_tier}_{infested_string}cabin_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="cabin_01,cabin_06,cabin_09,cabin_11,cabin_07,cabin_05,cabin_08,cabin_14,cabin_02,cabin_12,cabin_15,cabin_10,cabin_04,cabin_16{zztong_t1_cabins}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}cabin_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="cabin_01,cabin_06,cabin_09,cabin_11,cabin_07,cabin_05,cabin_08,cabin_14,cabin_02,cabin_12,cabin_15,cabin_10,cabin_04,cabin_16{zztong_t1_cabins}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Survivor Sites
    quest_id = f"tier{current_tier}_{infested_string}survivor_site_clear"
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
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="survivor_site_02,survivor_site_05,survivor_site_06,survivor_site_08,survivor_site_03,survivor_site_09,survivor_site_01,survivor_site_10,survivor_site_11,survivor_site_07" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}survivor_site_fetch"
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
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="survivor_site_02,survivor_site_05,survivor_site_06,survivor_site_08,survivor_site_03,survivor_site_09,survivor_site_01,survivor_site_10,survivor_site_11,survivor_site_07" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Fast Food
    quest_id = f"tier{current_tier}_{infested_string}fast_food_clear"
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
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="fastfood_03,fastfood_02,fastfood_01,fastfood_05" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}fast_food_fetch"
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
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="fastfood_03,fastfood_02,fastfood_01,fastfood_05" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Caves
    quest_id = f"tier{current_tier}_{infested_string}caves_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="cave_05,cave_01,cave_04,cave_03,cave_02{zztong_t1_caves}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}caves_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="cave_05,cave_01,cave_04,cave_03,cave_02{zztong_t1_caves}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Stores
    quest_id = f"tier{current_tier}_{infested_string}store_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="store_electronics_01,store_grocery_05,store_grocery_04,store_grocery_06,store_laundry_01,store_pharmacy_01{zztong_t1_stores}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}store_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="store_electronics_01,store_grocery_05,store_grocery_04,store_grocery_06,store_laundry_01,store_pharmacy_01{zztong_t1_stores}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Gas Station
    quest_id = f"tier{current_tier}_{infested_string}gas_station_clear"
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
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="gas_station_11,gas_station_04,gas_station_08,gas_station_10,gas_station_01,gas_station_09,fastfood_04,gas_station_03,gas_station_02,gas_station_07" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}gas_station_fetch"
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
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="gas_station_11,gas_station_04,gas_station_08,gas_station_10,gas_station_01,gas_station_09,fastfood_04,gas_station_03,gas_station_02,gas_station_07" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Diner
    quest_id = f"tier{current_tier}_{infested_string}diner_clear"
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
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="diner_01,diner_02,diner_03,diner_04" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}diner_fetch"
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
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="diner_01,diner_02,diner_03,diner_04" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Ranger Station
    quest_id = f"tier{current_tier}_{infested_string}ranger_station_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="ranger_station_02,ranger_station_03,ranger_station_04,ranger_station_05{zztong_t1_stations}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}ranger_station_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="ranger_station_02,ranger_station_03,ranger_station_04,ranger_station_05{zztong_t1_stations}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier1_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

if tier_2_pois:
    current_tier = 2

    # Farm
    current_poi = "farm"
    poi_objectives = f"farm_04,barn_03,farm_01,farm_14,farm_07,barn_02,farm_08,farm_11,farm_10,farm_03{zztong_t2_farm}"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier2_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier2_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier2_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier2_clear_and_defend_ending
    rewards = Rewards().tier2_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Stores
    current_poi = "store"
    poi_objectives = f"store_electronics_02,store_bakery_01,store_autoparts_01,body_shop_01,store_hardware_01,store_book_01,store_grocery_01,post_office_01{zztong_t2_store}"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier2_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier2_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier2_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier2_clear_and_defend_ending
    rewards = Rewards().tier2_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Cabins
    current_poi = "cabin"
    poi_objectives = "cabin_18,cabin_13,cabin_03,cabin_17"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier2_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier2_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier2_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier2_clear_and_defend_ending
    rewards = Rewards().tier2_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Offices
    current_poi = "office"
    poi_objectives = "office_03,office_02,office_04"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier2_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier2_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier2_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier2_clear_and_defend_ending
    rewards = Rewards().tier2_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

if tier_3_pois:
    current_tier = 3

    # Military Outposts
    current_poi = "military_outpost"
    poi_objectives = "army_barracks_01,army_camp_04,bombshelter_02,ranger_station_07,ranger_station_01"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier3_clear_and_defend_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Warehouses
    current_poi = "warehouse"
    poi_objectives = "warehouse_08,warehouse_05,warehouse_02"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier3_clear_and_defend_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Farm
    current_poi = "farm"
    poi_objectives = f"farm_05,farm_02,farm_13,farm_15{zztong_t3_farm}"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier3_clear_and_defend_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Apartments
    current_poi = "apartments"
    poi_objectives = "motel_04,apartments_03,motel_03"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier3_clear_and_defend_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))


    # Stores
    current_poi = "store"
    poi_objectives = f"store_grocery_03,store_discount_01,store_clothing_02,store_pharmacy_02,store_book_02,store_clothing_01,store_hardware_02{zztong_t3_store}"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_clear_ending
    rewards = Rewards().tier3_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_ending
    rewards = Rewards().tier3_fetch_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier3_clear_and_defend_ending
    rewards = Rewards().tier3_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

if tier_4_pois:
    current_tier = 4

    # Military Outpost
    current_poi = "military_outpost"
    poi_objectives = f"army_camp_02,army_camp_03,army_camp_05,army_camp_01{zztong_t4_army}"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier4_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier4_clear_and_defend_ending
    rewards = Rewards().tier4_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # City Building
    current_poi = "city_building"
    poi_objectives = f"skyscraper_04,city_center_01,downtown_strip_12,downtown_strip_11,downtown_strip_01,downtown_strip_02,downtown_strip_03,downtown_strip_04,downtown_building_02,downtown_strip_05,downtown_strip_07{zztong_t4_downtown}"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier4_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier4_clear_and_defend_ending
    rewards = Rewards().tier4_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Store
    current_poi = "store"
    poi_objectives = f"store_hardware_03,store_grocery_02,store_gun_01,store_gun_02{zztong_t4_store}"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier4_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier4_clear_and_defend_ending
    rewards = Rewards().tier4_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

if tier_5_pois:
    current_tier = 5

    # Skyscraper
    current_poi = "skyscraper"
    poi_objectives = f"skyscraper_01,skyscraper_02,skyscraper_03{zztong_t5_skyscraper}"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier6_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier5_clear_and_defend_ending
    rewards = Rewards().tier6_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    # Factory
    current_poi = "factory"
    poi_objectives = "factory_01,factory_02,factory_03"

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_fetch_and_clear"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_fetch_and_clear_ending
    rewards = Rewards().tier6_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

    quest_id = f"tier{current_tier}_{infested_string}{current_poi}_clear_and_defend"
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
    objectives = f"""
    <objective type="GotoPOIDEM, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />
        <property name="PrefabNames" value="{poi_objectives}" />
    </objective>
    """ + Objectives().objective_tier5_clear_and_defend_ending
    rewards = Rewards().tier6_fetch_and_clear_rewards
    quest_list.append(make_quest(quest_id, properties, objectives, rewards))

quest_list.write()
property_object.write()