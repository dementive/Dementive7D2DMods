class Objectives:
    def __init__(self):
        self.objective_fetch_ending = """xml
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
	</objective>
    	"""[
            3:
        ]

        self.objective_clear_ending = """xml
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
	</objective>
    	"""[
            3:
        ]

        self.objective_fetch_and_clear_ending = """xml
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
		</objective>
    	"""[
            3:
        ]
