"""QuestsExpanded's buffs, blocks and trader dialog: the bosses of the defense quests, the quest flags, and contracts
(their boons, the gamestage buff and the trader dialog options).

Run from anywhere: python config.py
Writes Config/buffs.xml, Config/blocks.xml and Config/dialogs.xml, and rewrites their rows of Config/Localization.csv,
in QuestsExpanded and ZZZTongPrefabs-QuestsExpanded.

A boon here must also be in ContractsDEM.Boons (src/Scripts/ContractsDEM.cs) for traders to offer it.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MODS = [os.path.join(HERE, ".."), os.path.join(HERE, "..", "..", "ZZZTongPrefabs-QuestsExpanded")]

# Localization rows this script owns (rewritten every run)
LOC_PREFIXES = ("buffDementiveBoon_", "buffDementiveContract", "dialog_dementive_", "ContractDEM_", "questFlagDEM",
                "questOutpostFlagDEM")

# Contract boons: name: (icon, effects, name, description)
BOONS = {
    "deadeye": ("ui_game_symbol_head_shot", ['<passive_effect name="EntityDamage" operation="perc_add" value=".15"/>'], "Deadeye", "+15% damage with every weapon."),
    "bloodthirst": ("ui_game_symbol_siphoning_strikes", ['<triggered_effect trigger="onSelfKilledOther" action="ModifyStats" stat="Health" operation="add" value="10"/>'], "Bloodthirst", "Every kill restores 10 health."),
    "secondwind": ("ui_game_symbol_cardio", ['<passive_effect name="StaminaChangeOT" operation="perc_add" value=".5"/>'], "Second Wind", "Stamina comes back 50% faster."),
    "scavenger": ("ui_game_symbol_mother_load", ['<passive_effect name="LootStage" operation="perc_add" value=".15"/>'], "Scavenger", "Better loot in containers (+15% loot stage)."),
    "ironhide": ("ui_game_symbol_armor_iron", ['<passive_effect name="PhysicalDamageResist" operation="base_add" value="10"/>'], "Ironhide", "+10 armor."),
    "fleetfoot": ("ui_game_symbol_run", ['<passive_effect name="RunSpeed" operation="perc_add" value=".1"/>',
                                         '<passive_effect name="WalkSpeed" operation="perc_add" value=".1"/>'], "Fleet Foot", "+10% walking and running speed."),
    "regeneration": ("ui_game_symbol_healing_factor", ['<passive_effect name="HealthChangeOT" operation="base_add" value=".2"/>'], "Regeneration", "Your wounds slowly heal on their own."),
    "glasscannon": ("ui_game_symbol_critical", ['<passive_effect name="EntityDamage" operation="perc_add" value=".3"/>',
                                                '<passive_effect name="HealthMax" operation="perc_add" value="-.2"/>'], "Glass Cannon", "+30% damage with every weapon, but -20% max health."),
    "adrenaline": ("ui_game_symbol_steroids", ['<passive_effect name="RunSpeed" operation="perc_add" value=".2"/>',
                                               '<passive_effect name="StaminaChangeOT" operation="perc_add" value=".5"/>',
                                               '<passive_effect name="PhysicalDamageResist" operation="base_add" value="-15"/>'], "Adrenaline Junkie", "+20% running speed and stamina comes back 50% faster, but -15 armor."),
    "juggernaut": ("ui_game_symbol_muscle", ['<passive_effect name="HealthMax" operation="perc_add" value=".25"/>',
                                             '<passive_effect name="PhysicalDamageResist" operation="base_add" value="15"/>',
                                             '<passive_effect name="RunSpeed" operation="perc_add" value="-.15"/>'], "Juggernaut", "+25% max health and +15 armor, but -15% running speed."),
}


def boon_buffs():
    out = []
    for name, (icon, effects, _, _) in BOONS.items():
        buff = f"buffDementiveBoon_{name}"
        out += [
            f'\t\t<buff name="{buff}" name_key="{buff}Name" description_key="{buff}Desc" tooltip_key="{buff}Name" icon="{icon}" icon_color="255,190,60">',
            '\t\t\t<stack_type value="ignore"/>',
            '\t\t\t<duration value="0"/>',
            '\t\t\t<effect_group>',
        ]
        out += ["\t\t\t\t" + effect for effect in effects]
        out += ['\t\t\t</effect_group>', '\t\t</buff>', '']
    return out


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

		<!-- The boss that hunts a player on the last stage of a contract, on top of buffDementiveBoss -->
		<buff name="buffDementiveContractBoss" hidden="true">
			<stack_type value="ignore"/>
			<duration value="0"/>

			<effect_group>
				<passive_effect name="HealthMax" operation="perc_add" value="1"/>
				<passive_effect name="EntityDamage" operation="perc_add" value=".25"/>
			</effect_group>

			<effect_group>
				<triggered_effect trigger="onSelfBuffStart" action="ModifyStats" stat="Health" operation="add" value="30000"/>
			</effect_group>
		</buff>

		<!-- A player on a contract: their gamestage goes up with every stage done (ContractsDEM sets the cvar) -->
		<buff name="buffDementiveContract" name_key="buffDementiveContractName" description_key="buffDementiveContractDesc" tooltip_key="buffDementiveContractName" icon="ui_game_symbol_skull" icon_color="255,190,60">
			<stack_type value="ignore"/>
			<duration value="0"/>

			<effect_group>
				<passive_effect name="GameStage" operation="perc_add" value="@dementiveContractGS"/>
			</effect_group>
		</buff>

		<!-- Contract boons, one picked from three after every stage; they last until the contract ends -->
@BOONS@	</append>

</Dementive>
'''

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
	</append>

</Dementive>
'''

BOON_IDS = list(BOONS)

DIALOGS = '''<Dementive>

	<!-- Contracts (ContractsDEM in QuestsExpanded.dll): start one, check on it, pick boons and cash out at any trader -->
	<insertBefore xpath="/dialogs/dialog[@id='trader']/statement[@id='start']/response_entry[@id='done']">
		<response_entry id="dementiveContract"/>
	</insertBefore>

	<append xpath="/dialogs/dialog[@id='trader']">
		<statement id="dementiveContract" text="dialog_dementive_contract_statement">
			<response_entry id="dementiveContractStart"/>
			<response_entry id="dementiveContractStatus"/>
			<response_entry id="dementiveContractBoons"/>
			<response_entry id="dementiveContractCashOut"/>
			<response_entry id="nevermind"/>
		</statement>

		<statement id="dementiveContractBoons" text="dialog_dementive_contract_boons_statement">
@BOON_ENTRIES@			<response_entry id="dementiveContractBack"/>
		</statement>

		<response id="dementiveContract" text="dialog_dementive_contract_response" nextstatementid="dementiveContract"/>

		<response id="dementiveContractStart" text="dialog_dementive_contract_start" nextstatementid="start">
			<requirement type="ContractDEM, QuestsExpanded" id="none" requirementtype="Hide"/>
			<action type="ContractDEM, QuestsExpanded" id="start"/>
		</response>

		<response id="dementiveContractStatus" text="dialog_dementive_contract_status" nextstatementid="dementiveContract">
			<requirement type="ContractDEM, QuestsExpanded" id="active" requirementtype="Hide"/>
			<action type="ContractDEM, QuestsExpanded" id="status"/>
		</response>

		<response id="dementiveContractBoons" text="dialog_dementive_contract_boons" nextstatementid="dementiveContractBoons">
			<requirement type="ContractDEM, QuestsExpanded" id="offer" requirementtype="Hide"/>
		</response>

		<response id="dementiveContractCashOut" text="dialog_dementive_contract_cashout" nextstatementid="start">
			<requirement type="ContractDEM, QuestsExpanded" id="cashout" requirementtype="Hide"/>
			<action type="ContractDEM, QuestsExpanded" id="cashout"/>
		</response>

		<response id="dementiveContractBack" text="dialog_trader_response_nevermind" nextstatementid="dementiveContract"/>

@BOON_RESPONSES@	</append>

</Dementive>
'''


def boon_entries():
    return "".join(f'\t\t\t<response_entry id="dementiveBoon_{b}"/>\n' for b in BOON_IDS)


def boon_responses():
    out = ""
    for b in BOON_IDS:
        out += (f'\t\t<response id="dementiveBoon_{b}" text="dialog_dementive_boon_{b}" nextstatementid="dementiveContract">\n'
                f'\t\t\t<requirement type="ContractDEM, QuestsExpanded" id="offered" value="{b}" requirementtype="Hide"/>\n'
                f'\t\t\t<action type="ContractDEM, QuestsExpanded" id="pick" value="{b}"/>\n'
                f'\t\t</response>\n\n')
    return out


OTHER_TEXT = {
    # Quest flags
    "questFlagDEM": ("blocks", "Block", "White River Flag"),
    "questFlagDEMDesc": ("blocks", "Block", "A White River flag from a trader's build kit. Plant it at the site of a Build and Defend or Last Stand quest to start the build. Planted in the wrong spot? Pick it up and plant it again."),
    "questOutpostFlagDEM": ("blocks", "Block", "Outpost Banner"),
    "questOutpostFlagDEMDesc": ("blocks", "Block", "The Duke's banner from a Create Outpost kit. Hang it inside the quest's building to claim it as an outpost. If it's destroyed or taken down, the outpost falls."),

    # Contracts
    "buffDementiveContractName": ("buffs", "Buff", "Contract"),
    "buffDementiveContractDesc": ("buffs", "Buff", "You're on a contract. The dead around you get tougher with every stage you finish (+10% gamestage per stage)."),
    "dialog_dementive_contract_response": ("Quest", "Dialogs", "Got any contracts?"),
    "dialog_dementive_contract_statement": ("Quest", "Dialogs", "A contract's for survivors who like a gamble. Do my jobs back to back, any jobs you like, and I'll hold your pay in a pot that grows with every one you finish, up to five. Cash out whenever you want. But if you die, fail a job or walk away from one, the whole pot's gone. And word is, by the fifth job something nasty comes looking for you."),
    "dialog_dementive_contract_start": ("Quest", "Dialogs", "Sign me up for a contract."),
    "dialog_dementive_contract_status": ("Quest", "Dialogs", "How's my contract looking?"),
    "dialog_dementive_contract_boons": ("Quest", "Dialogs", "I'll take my pick of the boons."),
    "dialog_dementive_contract_boons_statement": ("Quest", "Dialogs", "You've earned it. Pick one; it lasts until your contract's over."),
    "dialog_dementive_contract_cashout": ("Quest", "Dialogs", "I want to cash out my contract."),
    "ContractDEM_started": ("UI", "Quest", "Contract started! The rewards of your next jobs go into the pot."),
    "ContractDEM_stage": ("UI", "Quest", "Stage {0} done! Cash out now for {2}% of the pot, or push on. Pick a boon at any trader."),
    "ContractDEM_stage_last": ("UI", "Quest", "Stage {0} done! Cash out now for {2}% of the pot, or take on the last job... if you can survive what comes hunting you."),
    "ContractDEM_picked": ("UI", "Quest", "Boon taken: {1}."),
    "ContractDEM_lost_death": ("UI", "Quest", "You died. Your contract is over and the pot is lost."),
    "ContractDEM_lost_quest": ("UI", "Quest", "You failed a job. Your contract is over and the pot is lost."),
    "ContractDEM_cashout": ("UI", "Quest", "Contract cashed out: {0} XP, {1} dukes and {2} items."),
    "ContractDEM_complete": ("UI", "Quest", "Contract complete! Your payout: {0} XP, {1} dukes and {2} items."),
    "ContractDEM_status": ("UI", "Quest", "Contract: {0} of {1} stages done. In the pot: {2} XP, {3} dukes and {4} items. Cashing out now pays {5}%."),
    "ContractDEM_boss": ("UI", "Quest", "Something is hunting you..."),
    "ContractDEM_bossdead": ("UI", "Quest", "The hunter is dead. Grab its loot!"),
}


def csv_field(text):
    return '"' + text.replace('"', '""') + '"' if any(c in text for c in ',"') else text


def localization_rows():
    rows = []
    for name, (_, _, title, desc) in BOONS.items():
        buff = f"buffDementiveBoon_{name}"
        rows.append(f"{buff}Name,buffs,Buff,,,,{csv_field(title)},,,,,,,,,,,,,")
        rows.append(f"{buff}Desc,buffs,Buff,,,,{csv_field(desc)},,,,,,,,,,,,,")
        rows.append(f"dialog_dementive_boon_{name},Quest,Dialogs,,,,{csv_field(title + ': ' + desc)},,,,,,,,,,,,,")
    for key, (file, kind, text) in OTHER_TEXT.items():
        rows.append(f"{key},{file},{kind},,,,{csv_field(text)},,,,,,,,,,,,,")
    return rows


def write(path, text):
    open(path, "w", encoding="utf-8", newline="").write(text.replace("\r\n", "\n").replace("\n", "\r\n"))


def update_mod(mod_dir):
    config = os.path.join(mod_dir, "Config")
    write(os.path.join(config, "buffs.xml"), BUFFS.replace("@BOONS@", "\n".join(boon_buffs()) + "\n"))
    write(os.path.join(config, "blocks.xml"), BLOCKS)
    write(os.path.join(config, "dialogs.xml"),
          DIALOGS.replace("@BOON_ENTRIES@", boon_entries()).replace("@BOON_RESPONSES@", boon_responses()))

    loc_path = os.path.join(config, "Localization.csv")
    loc = open(loc_path, encoding="utf-8", newline="").read().replace("\r\n", "\n").rstrip("\n").split("\n")
    loc = [line for line in loc if not line.startswith(LOC_PREFIXES)] + localization_rows()
    open(loc_path, "w", encoding="utf-8", newline="").write("\r\n".join(loc) + "\r\n")


if __name__ == "__main__":
    for mod in MODS:
        update_mod(mod)
    print(f"buffs, blocks, dialogs and {len(BOONS)} contract boons written to {len(MODS)} mods")
