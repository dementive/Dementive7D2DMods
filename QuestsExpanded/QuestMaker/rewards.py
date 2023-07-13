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
	"""[3:]

		self.tier1_fetch_rewards = """xml
	<reward type="Exp" value="2500"/>
	<reward type="Item" id="casinoCoin" value="330"/>
	
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="1"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="1"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="1"/>
	<reward type="LootItem" id="groupQuestResources" ischosen="true" value="1"/>
	<reward type="LootItem" id="groupQuestAmmo,groupQuestResources,groupQuestMods,groupQuestT1SkillMagazineBundle" ischosen="true" value="1"/>
		"""[3:]

		self.tier2_clear_rewards = """xml
	<reward type="Exp" value="4500"/>
	<reward type="Item" id="casinoCoin" value="1350"/>

	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier2_fetch_rewards = """xml
	<reward type="Exp" value="3750"/>
	<reward type="Item" id="casinoCoin" value="560"/>

	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="2"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier3_clear_rewards = """xml
	<reward type="Exp" value="6000"/>
	<reward type="Item" id="casinoCoin" value="1800"/>

	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier3_fetch_rewards = """xml
	<reward type="Exp" value="5000"/>
	<reward type="Item" id="casinoCoin" value="800"/>

	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="3"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier4_clear_rewards = """xml
	<reward type="Exp" value="7500"/>
	<reward type="Item" id="casinoCoin" value="2040"/>

	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier4_fetch_rewards = """xml
	<reward type="Exp" value="6250"/>
	<reward type="Item" id="casinoCoin" value="1020"/>

	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="4"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier5_clear_rewards = """xml
	<reward type="Exp" value="15000"/>
	<reward type="Item" id="casinoCoin" value="4080"/>

	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier5_fetch_rewards = """xml
	<reward type="Exp" value="12500"/>
	<reward type="Item" id="casinoCoin" value="2040"/>

	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="5"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier6_clear_rewards = """xml
	<reward type="Exp" value="24000"/>
	<reward type="Item" id="casinoCoin" value="7200"/>

	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]

		self.tier6_fetch_rewards = """xml
	<reward type="Exp" value="20000"/>
	<reward type="Item" id="casinoCoin" value="6000"/>

	<reward type="LootItem" id="groupQuestTools" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestArmor,groupQuestMedical" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestAmmo" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestWeapons" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestSchematics" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestMods" ischosen="true" value="6"/>
	<reward type="LootItem" id="groupQuestSteel" ischosen="true"/>
	<reward type="LootItem" id="groupQuestT1SkillMagazineBundle" ischosen="true"/>
		"""[3:]