# Quest Localization Guide

All added quests need to follow the themes of the base game quests and should fit seemlessly alongside existing quests in game.

It is important to make sure that fetch quests get localization that is for fetching supplies and clear quests get localization for killing zombies.

# Base Game "lore"

The main settlement in the game seems to be the "White River settlement". This is basically the ring of traders plus a lot of other people we don't see in game, the White River settlement seems to be spread througout the entire map and they have people all over but we only ever hear from the traders in game. White River settlement is currently run by a guy named Duke, but a guy named Noah White originally founded the White River settlements in the area. Noah was probably a good guy and things were pretty good when he was around...but now Duke is in charge and he isn't so cool.

These are all the references to the White River settlement that seem relavent

"Dear Friend,\n\nThe wasteland can be an unforgiving place, I found you naked and left for dead with no supplies. It looks like you crossed the Duke in a bad way and you could use some help. Enclosed is a short guide to help you survive. If you complete it, we just might take in a new citizen. The White River Settlement: it's real and it's safe.\n\nPeace be with you friend, -Noah"

"Dear Friend,\nAs you know the wasteland can be an unforgiving place and from our observations you look like you could use some help. Here’s a little guide to help a newcomer survive.  Think of it as our little initiation. Complete it to our liking and we just might take in a new citizen. The White River Settlement, it’s real and it’s safe.\n\n Good Luck Noah"

"The founder of the White River Settler's Outposts, Noah White stood up to the Duke and is now on the run from the Cassadores."

"Go prove that you have what it takes to be a part of White River Runners. We need you to clear out the zombies at [DECEA3]{poi.name}[-]."

"This is very important to White River so I decided to send the best person for the job, unfortunately he's not available so I'll have to send you instead. Go slaughter the zombies at [DECEA3]{poi.name}[-]."

"Congratulations! I can make my payment to The Duke now."

This is all there is to go off of...not much.

# New "lore" from QuestsExpanded

Base Game Characters:

Noah White - White River founder

Duke - White River Leader (Ruler?Overlord?)

Bob - Trader, cool guy.
Hugh - Trader, cool guy.
Jen - Trader, female.
Joel - Trader, OG cool guy.
Rekt - Trader, asshole farmer.

If you write about any new White River characters put them here so a coherant "story" can be built.

John - White River special ops guy. Possibly former CIA member. Zombie killing machine.

# Localizaion Examples from the base game


## Name examples
quest_tier1_fetch_name,Quest,Quest Info,,,Tier 1 Fetch,
quest_tier1_clear_name,Quest,Quest Info,,,Tier 1 Clear

## Subtitle examples
quest_fetch_subtitle,Quest,Quest Info,,,Retrieve the Supplies
quest_clear_subtitle,Quest,Quest Info,,,Clear the Area
quest_fetch_clear_subtitle,Quest,Quest Info,,,Clear Area and Retrieve Supplies

## Description examples
quest_fetch_description,Quest,Quest Info,,,Head to [DECEA3]{poi.name}[-] and retrieve the shipment. Be careful we don't know what's in there.
quest_clear_description,Quest,Quest Info,,,Head to [DECEA3]{poi.name}[-] and clear out the zombies. This location could be useful to our cause.

## Offer examples
quest_tier1_fetch_offer,Quest,Quest Info,,,One of our operatives had to stash their shipment at [DECEA3]{poi.name}[-]. Go retrieve the shipment and return it to me.
quest_tier2_fetch_offer,Quest,Quest Info,,,My men ran into trouble and had to hide their supplies at [DECEA3]{poi.name}[-]. Go get the goods and return them to me.
quest_tier3_fetch_offer,Quest,Quest Info,,,The boys left their shipment at [DECEA3]{poi.name}[-]. I would appreciate it if you could return it to me.
quest_tier4_fetch_offer,Quest,Quest Info,,,One of our other outposts left some supplies at [DECEA3]{poi.name}[-]. I will reward you if you could get them back for me.
quest_tier5_fetch_offer,Quest,Quest Info,,,Some of our men went missing on a supply run at [DECEA3]{poi.name}[-]. I fear the worst but really need the supplies. Can you take care of this for me?
quest_tier6_fetch_offer,Quest,Quest Info,,,We got a tip about some supplies left at [DECEA3]{poi.name}[-]. This will be the toughest supply run we have sent you on. Bring home the bacon, we are counting on you.

quest_tier1_clear_offer,Quest,Quest Info,,,Go prove that you have what it takes to be a part of White River Runners. We need you to clear out the zombies at [DECEA3]{poi.name}[-].
quest_tier2_clear_offer,Quest,Quest Info,,,"You are ready for more, huh? Well this one will be a little harder but I'm sure you will manage. Go kill all the zombies at [DECEA3]{poi.name}[-].
quest_tier3_clear_offer,Quest,Quest Info,,,You did a great job on the last clearing but this one may be a bit tougher. I'm sure you can handle it. Go wipe out the zombies at [DECEA3]{poi.name}[-].
quest_tier4_clear_offer,Quest,Quest Info,,,You know the drill. Go exterminate all the zombies at [DECEA3]{poi.name}[-].
quest_tier5_clear_offer,Quest,Quest Info,,,"This is very important to White River so I decided to send the best person for the job, unfortunately he's not available so I'll have to send you instead. Go slaughter the zombies at [DECEA3]{poi.name}[-]."
quest_tier6_clear_offer,Quest,Quest Info,,,"This may be the toughest clear job yet, but I know I can count on you. Go finish off the zombies at [DECEA3]{poi.name}[-]. Good luck."

quest_tier2_fetch_clear_offer,Quest,Quest Info,,,One of our Runners had to stash their shipment at [DECEA3]{poi.name}[-]. Go exterminate the zombies and retrieve the shipment.

## Statement examples
quest_fetch_statement,Quest,Quest Info,,,Bring back the shipment.
quest_clear_statement,Quest,Quest Info,,,Clear out the zombies in the area.

## Response examples
quest_fetch_response,Quest,Quest Info,,,Fetch ([DECEA3]{poi.distance} {poi.direction}[-])
quest_clear_response,Quest,Quest Info,,,Clear Zombies ([DECEA3]{poi.distance} {poi.direction}[-])
quest_fetch_clear_response,Quest,Quest Info,,,Fetch / Clear ([DECEA3]{poi.distance} {poi.direction}[-])

## Completion examples
quest_fetch_completion,Quest,Quest Info,,,Well I'll be danged. You really managed to pull through in a pinch. Thanks for retrieving those supplies. Here's what I owe ya.
quest_clear_completion,Quest,Quest Info,,,Well I'll be danged. You really managed to pull through in a pinch. Thanks for killing all those zombies. Here's what I owe ya.


# Dynamic Links:

Zorgoxplanation: These are kind of like the brackets you find to game links in Imperator Loc like [GetRootScope.GetCountry.GetRuler]

# Dynamic Links to use in quests:

"[DECEA3]{poi.name}[-]" - This gets the name of the location the quest is sending the player to.
