from properties import properties
from objectives import Objectives
from rewards import Rewards
from quest import Quest

"""
    This is a slightly nicer way to write quests for 7 days to die since the regular quests.xml isn't nearly as flexible as python
"""

if __name__ == "__main__":
    quest_list = list()
    properties = properties(
        group_name_key="t1_urban_group_name",
        name_key="t1_urban_group_name",
        subtitle_key="t1_urban_group_subtitle",
        description_key="t1_urban_group_description",
        category_key="t1_urban_group_category",
        offer_key="t1_urban_group_offer",
        statement_key="t1_urban_group_statement",
        response_key="t1_urban_group_response",
        completion_key="t1_urban_group_completion",
        icon="t1_urban_group_name",
        difficulty="easy",
        difficulty_tier="1",
        reward_choices_count="5",
        login_rally_reset="true",
        repeatable="true",
        shareable="true",
        completiontype="TurnIn"
    )
    objectives = """xml
    <objective type="RandomTaggedPOIGotoSDX, QuestsExpanded">
        <property name="phase" value="1" />
        <property name="nav_object" value="quest" />

        <!-- Include POIs only if they have any of these tags -->
        <property name="include_tags" value="downtown,industrial" />
    </objective>
    """[3:] + Objectives().objective_clear_ending
    rewards = Rewards().tier1_clear_rewards
    t1_urban_clear = Quest("t1_urban_clear", properties, objectives, rewards)
    quest_list.append(t1_urban_clear.quest)
    print(quest_list[0])