"""QuestsExpanded's buffs and blocks: the bosses and marked zombies of the defense quests, the marker on NPCs waiting
for a player in the NPC quests, and the quest flags.

Run from anywhere: python config.py
Writes Config/buffs.xml and Config/blocks.xml, and rewrites their rows of Config/Localization.csv, in QuestsExpanded.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MODS = [os.path.join(HERE, "..")]

# Localization rows this script owns (rewritten every run)
LOC_PREFIXES = ("questFlagDEM", "questOutpostFlagDEM", "questSafehouseFlagDEM")

BUFFS = '''<Dementive>

	<append xpath="/buffs">
		<!-- Bosses of the defense quests (WaveDirectorDEM in QuestsExpanded.dll): tougher, bigger, explosion
		resistant, with a health bar overhead and a marker on the map and compass. Max health only goes up after the
		buff starts, so health is topped up to the new max then, like vanilla's tough Twitch vote zombies. -->
		<buff name="buffDementiveBoss" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>

			<effect_group>
				<passive_effect name="HealthMax" operation="perc_add" value="1.5"/>
				<passive_effect name="ExplosionIncomingDamage" operation="perc_add" value="-0.5"/>
			</effect_group>

			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyStats" stat="Health" operation="add" value="30000"/>
				<triggered_effect trigger="onSelfBuffStart" action="SetScale" scale="1.2"/>
				<triggered_effect trigger="onSelfBuffStart" action="SetNavObject" nav_object="twitch_vote_boss" add="true"/>
				<triggered_effect trigger="onSelfBuffStart" action="SetNavObject" nav_object="zombie" add="true"/>
			</effect_group>
		</buff>

		<!-- The last few zombies of a defense wave: shown on the map and compass so nobody has to hunt for them -->
		<buff name="buffDementiveMarked" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>

			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="SetNavObject" nav_object="zombie" add="true"/>
			</effect_group>
		</buff>

		<!-- Survivors and refugees of the NPC quests waiting for a player to come and get them: shown on the map and
		compass. Removed when they follow someone. -->
		<buff name="buffDementiveWaiting" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>

			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="SetNavObject" nav_object="fetch_container" add="true"/>
				<triggered_effect trigger="onSelfBuffRemove" action="SetNavObject" nav_object="fetch_container" add="false"/>
			</effect_group>
		</buff>
	</append>

</Dementive>
'''

BUFFS = BUFFS.replace('''
</Dementive>
''', '''
	<!-- SCore's NPCs take no damage while they have a buff with this name, but SCore doesn't define one. The NPC
	quests use it to keep survivors and refugees alive until a player has come for them (NpcDefensesDEM). Added only
	if no mod loaded before this one defines it. -->
	<append xpath="/buffs[not(buff[@name='buffInvulnerable'])]">
		<buff name="buffInvulnerable" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>
		</buff>
	</append>

</Dementive>
''')

BLOCKS = '''<Dementive>

	<append xpath="/blocks">
		<!-- The flag Build and Defend and Last Stand quests hand out in their kit. Planting it near the quest's site
		starts the build phase, and the waves come at it (BlockQuestFlagDEM in QuestsExpanded.dll). -->
		<block name="questFlagDEM">
			<property name="Extends" value="flagPoleWhiteRiver"/>
			<property name="CreativeMode" value="None"/>
			<property name="Class" value="QuestFlagDEM, QuestsExpanded"/>
			<property name="CustomIcon" value="flagPoleWhiteRiver"/>
			<!-- Planted in the wrong spot? Pick it up and plant it again -->
			<property name="CanPickup" value="true"/>
			<property name="DescriptionKey" value="questFlagDEMDesc"/>
		</block>

		<!-- The Duke's banner Create Outpost quests hand out: hung inside the POI, it is the outpost. If it is
		destroyed (or taken down) the outpost falls, so it is a lot tougher than a cloth banner. -->
		<block name="questOutpostFlagDEM">
			<property name="Extends" value="flagWallHungDuke"/>
			<property name="CreativeMode" value="None"/>
			<property name="Class" value="QuestFlagDEM, QuestsExpanded"/>
			<property name="CustomIcon" value="flagWallHungDuke"/>
			<property name="CanPickup" value="true"/>
			<property name="MaxDamage" value="2000"/>
			<property name="DescriptionKey" value="questOutpostFlagDEMDesc"/>
		</block>

		<!-- The flag Safehouse quests hand out: planted wherever the player wants the safehouse, it is the safehouse's
		middle (the checklist counts what's within 10m of it, and the refugees settle in around it). -->
		<block name="questSafehouseFlagDEM">
			<property name="Extends" value="flagWallHungHonorDuty"/>
			<property name="CreativeMode" value="None"/>
			<property name="Class" value="QuestFlagDEM, QuestsExpanded"/>
			<property name="CustomIcon" value="flagWallHungHonorDuty"/>
			<property name="CanPickup" value="true"/>
			<property name="DescriptionKey" value="questSafehouseFlagDEMDesc"/>
		</block>
	</append>

</Dementive>
'''

FLAG_TEXT = {
    "questFlagDEM": "White River Flag",
    "questFlagDEMDesc": "A White River flag from a trader's build kit. Plant it at the site of a Build and Defend or Last Stand quest to start the build. Planted in the wrong spot? Pick it up and plant it again.",
    "questOutpostFlagDEM": "Outpost Banner",
    "questOutpostFlagDEMDesc": "The Duke's banner from a Create Outpost kit. Hang it inside the quest's building to claim it as an outpost. If it's destroyed or taken down, the outpost falls.",
    "questSafehouseFlagDEM": "Safehouse Flag",
    "questSafehouseFlagDEMDesc": "The flag from a Safehouse quest. Hang it where you want the refugees' safehouse: everything the safehouse needs has to be within 10 blocks of it.",
}


def csv_field(text):
    return '"' + text.replace('"', '""') + '"' if any(c in text for c in ',"') else text


def localization_rows():
    return [f"{key},blocks,Block,,,,{csv_field(text)},,,,,,,,,,,,," for key, text in FLAG_TEXT.items()]


def write(path, text):
    open(path, "w", encoding="utf-8", newline="").write(text.replace("\r\n", "\n").replace("\n", "\r\n"))


def update_mod(mod_dir):
    config = os.path.join(mod_dir, "Config")
    write(os.path.join(config, "buffs.xml"), BUFFS)
    write(os.path.join(config, "blocks.xml"), BLOCKS)

    loc_path = os.path.join(config, "Localization.csv")
    loc = open(loc_path, encoding="utf-8", newline="").read().replace("\r\n", "\n").rstrip("\n").split("\n")
    loc = [line for line in loc if not line.startswith(LOC_PREFIXES)] + localization_rows()
    open(loc_path, "w", encoding="utf-8", newline="").write("\r\n".join(loc) + "\r\n")


if __name__ == "__main__":
    for mod in MODS:
        update_mod(mod)
    print(f"buffs and blocks written to {len(MODS)} mods")
