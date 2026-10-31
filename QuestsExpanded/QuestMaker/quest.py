import re

def make_quest(
	quest_id,
	properties="",
	objectives="",
	rewards=""
):
	# Infested quests reuse the normal objective endings but get the infestation rally marker
	if 'name="extra_tags" value="infested"' in properties:
		objectives = re.sub(r"questRallyMarker\w+", "questRallyMarkerInfestation", objectives)
	quest = f"<quest id=\"{quest_id}\">\n"
	quest += f"{properties}{objectives}{rewards}"
	quest += "\n</quest>\n"
	return (quest_id, quest)

class QuestList(list):
	def write(self):
		with open("quests.xml", "w") as file:
			file.write("")
		with open("quests.xml", "a") as file:
			for i in self:
				file.write(i[1])
		with open("quest_ids.txt", "w") as file:
			file.write("")
		with open("quest_ids.txt", "a") as file:
			for i in self:
				file.write(i[0])
				file.write("\n")
