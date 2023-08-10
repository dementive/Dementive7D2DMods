def write_to_file(buffs, entity_type, health_max, physical_damage_resist, size="1.25"):
    with open("zombies.xml", "a") as file:
        for buff in buffs:
            radiated = ",radiated" if buff == "zombie_enemyrad" else ""
            radiated_effect = (
                """  <triggered_effect trigger="onOtherDamagedSelf" action="ModifyCVar" target="self" cvar="RadiatedRegenAmount" operation="set" value="2.5"/>
                      <triggered_effect trigger="onOtherDamagedSelf" action="AddBuff" target="self" buff="buffRadiatedRegen"/>
                """
                if buff == "zombie_enemyrad"
                else ""
            )
            shock_buff = (
                f'\n                      <triggered_effect trigger="onSelfFirstSpawn" action="AddBuff" target="self" buff="zombie_headshock"/>'
                if buff == "zombie_enemyshock"
                else ""
            )
            file.write(
                f"""
                <entity_class name="{buff.replace("_", "")}{entity_type}" extends="zombieGuppy{entity_type}">
                    <property name="Tags" value="entity,zombie,walker,feral{radiated}"/>
                    <property name="ExperienceGain" value="600"/>
                    <property name="MoveSpeed" value="0.12"/>
                    <property name="MoveSpeedRand" value="-.2, .3"/>
                    <property name="SizeScale" value="{size}"/>
                    <property name="PainResistPerHit" value=".55"/>
                    <property name="LootDropEntityClass" value="EntityLootContainerStrong"/>
                    <effect_group name="Base Effects">
                      <triggered_effect trigger="onSelfFirstSpawn" action="AddBuff" target="self" buff="{buff}"/>{shock_buff}
                      <passive_effect name="DistractionResistance" operation="base_set" value="0,0"/>
                      <passive_effect name="HealthMax" operation="base_set" value="{health_max}"/>
                      <passive_effect name="HealthMax" operation="perc_set" value="1"/>
                      <passive_effect name="StaminaMax" operation="base_set"  value="100"/>
                      <passive_effect name="PhysicalDamageResist" operation="base_set" value="{physical_damage_resist}"/>
                    {radiated_effect}</effect_group>
                </entity_class>"""
            )


if __name__ == "__main__":
    buffs = [
        "zombie_enemyrad",
        "zombie_enemyshock",
        "zombie_enemyburn",
    ]
    with open("zombies.xml", "w") as file:
        file.write("")
    # Guppy Baby
    write_to_file(buffs, "BabyBoomer", "250", "10")
    # Guppy Alma
    write_to_file(buffs, "Alma", "250", "0", size="1.0")
    # Normal Guppy Zombies
    write_to_file(buffs, "BeatCop", "300", "25")
    write_to_file(buffs, "Belle", "300", "25")
    write_to_file(buffs, "Billy", "300", "25")
    write_to_file(buffs, "Bob", "300", "25")
    write_to_file(buffs, "Carmela", "300", "25")
    write_to_file(buffs, "Cheerleader", "300", "25")
    write_to_file(buffs, "HungryGeorge", "300", "25")
    write_to_file(buffs, "HungryJeff", "300", "25")
    write_to_file(buffs, "HungryScott", "300", "25")
    write_to_file(buffs, "Lucy", "300", "25")
    write_to_file(buffs, "Nurse", "300", "25")
    write_to_file(buffs, "OldManZombie", "300", "25")
    write_to_file(buffs, "Pete", "300", "25")
    write_to_file(buffs, "PoliceRalph", "300", "25")
    write_to_file(buffs, "Roland", "300", "25")
    write_to_file(buffs, "SecurityGuard", "300", "25")
    write_to_file(buffs, "Seth", "300", "25")
    write_to_file(buffs, "Stripper", "300", "25")
    write_to_file(buffs, "Thorton", "300", "25")
    write_to_file(buffs, "Emaciated", "300", "25")
    write_to_file(buffs, "Bones", "300", "25")
    write_to_file(buffs, "Glenda", "300", "25")
    write_to_file(buffs, "Bonnie", "300", "25")
    write_to_file(buffs, "Jessica", "300", "25")
    write_to_file(buffs, "Travis", "300", "25")
    write_to_file(buffs, "Chris", "300", "25")
    write_to_file(buffs, "Dillon", "300", "25")
    write_to_file(buffs, "Betty", "300", "25")
    write_to_file(buffs, "Burnt", "300", "25")
    write_to_file(buffs, "Cletus", "300", "25")
    write_to_file(buffs, "Doom", "300", "25")
    write_to_file(buffs, "NoArms", "300", "25")
    write_to_file(buffs, "RiotGear", "300", "25")
    # Medium Guppy Zombies
    write_to_file(buffs, "GermanCosplay", "500", "25")
    # Biomechanical Wight
    write_to_file(buffs, "BiomechanicalWight", "900", "80", size="1.0")
    # Guppy Clot
    write_to_file(buffs, "Clot", "950", "35")
    # Guppy Kenneth Clown
    write_to_file(buffs, "KennethClown", "1500", "70", size="1.0")
    # Guppy Radiated
    write_to_file(buffs, "Radiated", "800", "35")
