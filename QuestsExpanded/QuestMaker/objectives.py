class Objectives:
    def __init__(self):
        self.objective_fetch_ending = """
	<objective type="RallyPoint">
		<property name="phase" value="2"/>
		<property name="nav_object" value="rally" />
	</objective>

	<objective type="FetchFromContainer">
		<property name="phase" value="3"/>
		<property name="quest_item_ID" value="1"/>
		<property name="item_count" value="1"/>
		<property name="default_container" value="cntFetchQuestSatchel"/>
		<property name="nav_object" value="fetch_container" />
	</objective>

	<objective type="POIStayWithin">
		<property name="phase" value="3"/>
		<property name="radius" value="25"/>
	</objective>

	<action type="UnlockPOI" >
		<property name="phase" value="4"/>
	</action>

	<objective type="ReturnToNPC">
		<property name="phase" value="4"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>

	<objective type="InteractWithNPC">
		<property name="phase" value="4"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>"""

        self.objective_clear_ending = """
	<objective type="RallyPoint">
		<property name="phase" value="2"/>
		<property name="nav_object" value="rally" />
	</objective>

	<objective type="ClearSleepers">
		<property name="phase" value="3"/>
		<property name="nav_object" value="sleeper_volume"/>
	</objective>

	<objective type="POIStayWithin">
		<property name="phase" value="3"/>
		<property name="radius" value="25"/>
	</objective>

	<action type="UnlockPOI" >
		<property name="phase" value="4"/>
	</action>

	<objective type="ReturnToNPC">
		<property name="phase" value="4"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>

	<objective type="InteractWithNPC">
		<property name="phase" value="4"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>"""

        self.objective_fetch_and_clear_ending = """
	<objective type="RallyPoint">
		<property name="phase" value="2"/>
		<property name="nav_object" value="rally" />
	</objective>

	<objective type="ClearSleepers">
		<property name="phase" value="3"/>
		<property name="nav_object" value="sleeper_volume"/>
	</objective>

	<objective type="FetchFromContainer">
		<property name="phase" value="3"/>
		<property name="quest_item_ID" value="1"/>
		<property name="item_count" value="1"/>
		<property name="default_container" value="cntFetchQuestSatchel"/>
		<property name="nav_object" value="fetch_container" />
	</objective>

	<objective type="POIStayWithin">
		<property name="phase" value="3"/>
		<property name="radius" value="25"/>
	</objective>

	<action type="UnlockPOI" >
		<property name="phase" value="4"/>
	</action>

	<objective type="ReturnToNPC">
		<property name="phase" value="4"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>

	<objective type="InteractWithNPC">
		<property name="phase" value="4"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>"""

        self.objective_tier2_clear_and_defend_ending = """
	<objective type="RallyPoint">
		<property name="phase" value="2"/>
		<property name="nav_object" value="rally" />
	</objective>

	<objective type="ClearSleepers">
		<property name="phase" value="3"/>
		<property name="nav_object" value="sleeper_volume"/>
	</objective>

	<objective type="POIStayWithin">
		<property name="phase" value="3"/>
		<property name="radius" value="25"/>
	</objective>

	<action type="SpawnEnemy" id="zombieBoe,zombieFemaleFat,zombieJoe,zombieJanitor,zombieMoe,zombieArlene,zombieLab,zombieDarlene,zombieMarlene,zombieYo,zombieSteve,zombieBusinessMan" value="5-7" phase="4"/>
	<objective type="ObjectiveEntityKill" value="4" phase="4"/>
	<objective type="POIStayWithin">
		<property name="phase" value="4"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieBurnt,zombieNurse,zombieFatHawaiian,zombieMaleHazmat,zombieUtilityWorker,zombieSkateboarder,zombieCheerleader,zombieOldTimer,zombieFarmer,zombieStripper" value="5-7" phase="5"/>
	<objective type="ObjectiveEntityKill" value="4" phase="5"/>
	<objective type="POIStayWithin">
		<property name="phase" value="5"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieBiker" value="1" phase="6"/>
	<action type="SpawnEnemy" id="zombieSoldier" value="1" phase="6"/>
	<action type="SpawnEnemy" id="zombieJoe,zombieJanitor,zombieMoe,zombieArlene,zombieLab,zombieDarlene,zombieBurnt,zombieNurse,zombieFatHawaiian" value="4-6" phase="5"/>
	<objective type="ObjectiveEntityKill" value="6" phase="6"/>
	<objective type="POIStayWithin">
		<property name="phase" value="6"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="UnlockPOI" >
		<property name="phase" value="7"/>
	</action>

	<objective type="ReturnToNPC">
		<property name="phase" value="7"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>

	<objective type="InteractWithNPC">
		<property name="phase" value="7"/>
	</objective>"""

        self.objective_tier3_clear_and_defend_ending = """
	<objective type="RallyPoint">
		<property name="phase" value="2"/>
		<property name="nav_object" value="rally" />
	</objective>

	<objective type="ClearSleepers">
		<property name="phase" value="3"/>
		<property name="nav_object" value="sleeper_volume"/>
	</objective>

	<objective type="POIStayWithin">
		<property name="phase" value="3"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieBoe,zombieFemaleFat,zombieJoe,zombieJanitor,zombieMoe,zombieArlene,zombieLab,zombieDarlene,zombieMarlene,zombieYo,zombieSteve,zombieBusinessMan" value="4-6" phase="4"/>
	<action type="SpawnEnemy" id="zombieStripperFeral,zombieFarmerFeral,zombieOldTimerFeral,zombieCheerleaderFeral,zombieSkateboarderFeral,zombieUtilityWorkerFeral,zombieFatHawaiianFeral,zombieNurseFeral,zombieSnowFeral,zombieYoFeral,zombieBusinessManFeral,zombieMarleneFeral,zombieMoeFeral,zombieDarleneFeral,zombieSteveFeral,zombieLabFeral,zombieJoeFeral,zombieJanitorFeral,zombieBoeFeral,zombieFemaleFatFeral,zombieArleneFeral" value="2-3" phase="4"/>
	<objective type="ObjectiveEntityKill" value="5" phase="4"/>
	<objective type="POIStayWithin">
		<property name="phase" value="4"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieBurnt,zombieNurse,zombieFatHawaiian,zombieMaleHazmat,zombieUtilityWorker,zombieSkateboarder,zombieCheerleader,zombieOldTimer,zombieFarmer,zombieStripper" value="5-7" phase="5"/>
	<action type="SpawnEnemy" id="zombieStripperFeral,zombieFarmerFeral,zombieOldTimerFeral,zombieCheerleaderFeral,zombieSkateboarderFeral,zombieUtilityWorkerFeral,zombieFatHawaiianFeral,zombieNurseFeral,zombieSnowFeral,zombieYoFeral,zombieBusinessManFeral,zombieMarleneFeral,zombieMoeFeral,zombieDarleneFeral,zombieSteveFeral,zombieLabFeral,zombieJoeFeral,zombieJanitorFeral,zombieBoeFeral,zombieFemaleFatFeral,zombieArleneFeral" value="2-4" phase="5"/>
	<objective type="ObjectiveEntityKill" value="6" phase="5"/>
	<objective type="POIStayWithin">
		<property name="phase" value="5"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieSpider,zombieFatCop,zombieFatCopFeral,animalZombieDog" value="1" phase="6"/>
	<action type="SpawnEnemy" id="zombieBurnt,zombieNurse,zombieFatHawaiian,zombieMaleHazmat,zombieUtilityWorker,zombieSkateboarder,zombieCheerleader,zombieOldTimer,zombieFarmer,zombieStripper" value="2-3" phase="6"/>
	<action type="SpawnEnemy" id="zombieStripperFeral,zombieFarmerFeral,zombieOldTimerFeral,zombieCheerleaderFeral,zombieSkateboarderFeral,zombieUtilityWorkerFeral,zombieFatHawaiianFeral,zombieNurseFeral,zombieSnowFeral,zombieYoFeral,zombieBusinessManFeral,zombieMarleneFeral,zombieMoeFeral,zombieDarleneFeral,zombieSteveFeral,zombieLabFeral,zombieJoeFeral,zombieJanitorFeral,zombieBoeFeral,zombieFemaleFatFeral,zombieArleneFeral" value="2-3" phase="6"/>
	<objective type="ObjectiveEntityKill" value="5" phase="7"/>
	<objective type="POIStayWithin">
		<property name="phase" value="7"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="UnlockPOI" >
		<property name="phase" value="8"/>
	</action>

	<objective type="ReturnToNPC">
		<property name="phase" value="8"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>

	<objective type="InteractWithNPC">
		<property name="phase" value="8"/>
	</objective>
	"""

        self.objective_tier4_clear_and_defend_ending = """
	<objective type="RallyPoint">
		<property name="phase" value="2"/>
		<property name="nav_object" value="rally" />
	</objective>

	<objective type="ClearSleepers">
		<property name="phase" value="3"/>
		<property name="nav_object" value="sleeper_volume"/>
	</objective>

	<objective type="POIStayWithin">
		<property name="phase" value="3"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieBoe,zombieFemaleFat,zombieJoe,zombieJanitor,zombieMoe,zombieArlene,zombieLab,zombieDarlene,zombieMarlene,zombieYo,zombieSteve,zombieBusinessMan" value="2-3" phase="4"/>
	<action type="SpawnEnemy" id="zombieStripperFeral,zombieFarmerFeral,zombieOldTimerFeral,zombieCheerleaderFeral,zombieSkateboarderFeral,zombieUtilityWorkerFeral,zombieFatHawaiianFeral,zombieNurseFeral,zombieSnowFeral,zombieYoFeral,zombieBusinessManFeral,zombieMarleneFeral,zombieMoeFeral,zombieDarleneFeral,zombieSteveFeral,zombieLabFeral,zombieJoeFeral,zombieJanitorFeral,zombieBoeFeral,zombieFemaleFatFeral,zombieArleneFeral" value="3-4" phase="4"/>
	<objective type="ObjectiveEntityKill" value="5" phase="4"/>
	<objective type="POIStayWithin">
		<property name="phase" value="4"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieBurnt,zombieNurse,zombieFatHawaiian,zombieMaleHazmat,zombieUtilityWorker,zombieSkateboarder,zombieCheerleader,zombieOldTimer,zombieFarmer,zombieStripper" value="3" phase="5"/>
	<action type="SpawnEnemy" id="zombieStripperFeral,zombieFarmerFeral,zombieOldTimerFeral,zombieCheerleaderFeral,zombieSkateboarderFeral,zombieUtilityWorkerFeral,zombieFatHawaiianFeral,zombieNurseFeral,zombieSnowFeral,zombieYoFeral,zombieBusinessManFeral,zombieMarleneFeral,zombieMoeFeral,zombieDarleneFeral,zombieSteveFeral,zombieLabFeral,zombieJoeFeral,zombieJanitorFeral,zombieBoeFeral,zombieFemaleFatFeral,zombieArleneFeral" value="3" phase="5"/>
	<objective type="ObjectiveEntityKill" value="5" phase="5"/>
	<objective type="POIStayWithin">
		<property name="phase" value="5"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieWightFeral,zombieBikerFeral,zombieSoldierFeral,zombieSpiderFeral,zombieFatCopFeral" value="2" phase="5"/>
	<action type="SpawnEnemy" id="zombieBurnt,zombieNurse,zombieFatHawaiian,zombieMaleHazmat,zombieUtilityWorker,zombieSkateboarder,zombieCheerleader,zombieOldTimer,zombieFarmer,zombieStripper" value="2-3" phase="6"/>
	<action type="SpawnEnemy" id="zombieStripperFeral,zombieFarmerFeral,zombieOldTimerFeral,zombieCheerleaderFeral,zombieSkateboarderFeral,zombieUtilityWorkerFeral,zombieFatHawaiianFeral,zombieNurseFeral,zombieSnowFeral,zombieYoFeral,zombieBusinessManFeral,zombieMarleneFeral,zombieMoeFeral,zombieDarleneFeral,zombieSteveFeral,zombieLabFeral,zombieJoeFeral,zombieJanitorFeral,zombieBoeFeral,zombieFemaleFatFeral,zombieArleneFeral" value="2" phase="6"/>
	<objective type="ObjectiveEntityKill" value="6" phase="6"/>
	<objective type="POIStayWithin">
		<property name="phase" value="6"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="UnlockPOI" >
		<property name="phase" value="7"/>
	</action>

	<objective type="ReturnToNPC">
		<property name="phase" value="7"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>

	<objective type="InteractWithNPC">
		<property name="phase" value="7"/>
	</objective>
	"""

        self.objective_tier5_clear_and_defend_ending = """
	<objective type="RallyPoint">
		<property name="phase" value="2"/>
		<property name="nav_object" value="rally" />
	</objective>

	<objective type="ClearSleepers">
		<property name="phase" value="3"/>
		<property name="nav_object" value="sleeper_volume"/>
	</objective>

	<objective type="POIStayWithin">
		<property name="phase" value="3"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieBoe,zombieFemaleFat,zombieJoe,zombieJanitor,zombieMoe,zombieArlene,zombieLab,zombieDarlene,zombieMarlene,zombieYo,zombieSteve,zombieBusinessMan" value="2-4" phase="4"/>
	<action type="SpawnEnemy" id="zombieStripperFeral,zombieFarmerFeral,zombieOldTimerFeral,zombieCheerleaderFeral,zombieSkateboarderFeral,zombieUtilityWorkerFeral,zombieFatHawaiianFeral,zombieNurseFeral,zombieSnowFeral,zombieYoFeral,zombieBusinessManFeral,zombieMarleneFeral,zombieMoeFeral,zombieDarleneFeral,zombieSteveFeral,zombieLabFeral,zombieJoeFeral,zombieJanitorFeral,zombieBoeFeral,zombieFemaleFatFeral,zombieArleneFeral" value="3" phase="4"/>
	<action type="SpawnEnemy" id="zombieOldTimerRadiated,zombieCheerleaderRadiated,zombieSkateboarderRadiated,zombieMarleneRadiated,zombieSteveRadiated,zombieYoRadiated,zombieDarleneRadiated,zombieLabRadiated,zombieArleneRadiated,zombieMoeRadiated,zombieJanitorRadiated,zombieFemaleFatRadiated,zombieJoeRadiated,zombieBoeRadiated" value="1" phase="4"/>
	<objective type="ObjectiveEntityKill" value="6" phase="4"/>
	<objective type="POIStayWithin">
		<property name="phase" value="4"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieBurnt,zombieNurse,zombieFatHawaiian,zombieMaleHazmat,zombieUtilityWorker,zombieSkateboarder,zombieCheerleader,zombieOldTimer,zombieFarmer,zombieStripper" value="2-4" phase="5"/>
	<action type="SpawnEnemy" id="zombieStripperFeral,zombieFarmerFeral,zombieOldTimerFeral,zombieCheerleaderFeral,zombieSkateboarderFeral,zombieUtilityWorkerFeral,zombieFatHawaiianFeral,zombieNurseFeral,zombieSnowFeral,zombieYoFeral,zombieBusinessManFeral,zombieMarleneFeral,zombieMoeFeral,zombieDarleneFeral,zombieSteveFeral,zombieLabFeral,zombieJoeFeral,zombieJanitorFeral,zombieBoeFeral,zombieFemaleFatFeral,zombieArleneFeral" value="2-3" phase="5"/>
	<action type="SpawnEnemy" id="zombieOldTimerRadiated,zombieCheerleaderRadiated,zombieSkateboarderRadiated,zombieMarleneRadiated,zombieSteveRadiated,zombieYoRadiated,zombieDarleneRadiated,zombieLabRadiated,zombieArleneRadiated,zombieMoeRadiated,zombieJanitorRadiated,zombieFemaleFatRadiated,zombieJoeRadiated,zombieBoeRadiated" value="2" phase="5"/>
	<objective type="ObjectiveEntityKill" value="6" phase="5"/>
	<objective type="POIStayWithin">
		<property name="phase" value="5"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieWightRadiated,zombieBikerRadiated,zombieFatCopRadiated,zombieSpiderRadiated,zombieSoldierRadiated,zombieDemolition" value="4" phase="6"/>
	<action type="SpawnEnemy" id="zombieBurnt,zombieNurse,zombieFatHawaiian,zombieMaleHazmat,zombieUtilityWorker,zombieSkateboarder,zombieCheerleader,zombieOldTimer,zombieFarmer,zombieStripper" value="1-3" phase="6"/>
	<action type="SpawnEnemy" id="zombieOldTimerRadiated,zombieCheerleaderRadiated,zombieSkateboarderRadiated,zombieMarleneRadiated,zombieSteveRadiated,zombieYoRadiated,zombieDarleneRadiated,zombieLabRadiated,zombieArleneRadiated,zombieMoeRadiated,zombieJanitorRadiated,zombieFemaleFatRadiated,zombieJoeRadiated,zombieBoeRadiated" value="4" phase="6"/>
	<objective type="ObjectiveEntityKill" value="7" phase="6"/>
	<objective type="POIStayWithin">
		<property name="phase" value="6"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="SpawnEnemy" id="zombieWightRadiated,zombieBikerRadiated,zombieFatCopRadiated,zombieSpiderRadiated,zombieSoldierRadiated,zombieDemolition" value="3" phase="7"/>
	<objective type="POIStayWithin">
		<property name="phase" value="7"/>
		<property name="radius" value="25"/>
	</objective>
	
	<action type="UnlockPOI" >
		<property name="phase" value="8"/>
	</action>

	<objective type="ReturnToNPC">
		<property name="phase" value="8"/>
		<property name="nav_object" value="return_to_trader" />
	</objective>

	<objective type="InteractWithNPC">
		<property name="phase" value="8"/>
	</objective>
	"""
