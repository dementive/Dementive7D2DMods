class Rewards:
    def __init__(self):
        self.tier1_clear_rewards = """xml
	<reward type="Exp" value="3000"/>
	<reward type="Item" id="casinoCoin" value="800"/>

	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="1"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="1"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="1"/>
	<reward type="LootItem" id="groupQuestResources" ischosen="true" value="1"/>
	<reward type="LootItem" id="groupQuestAmmo,groupQuestResources,groupQuestMods,groupQuestT1SkillMagazineBundle" ischosen="true" value="1"/>
		"""[
            3:
        ]
