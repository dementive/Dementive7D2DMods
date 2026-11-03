using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

/// <summary>
/// Where you hit them, and what their mutations and gear do with a hit. A hit's damage response is worked out by the
/// game that lands it and then replayed on every other game (server and players) through ProcessDamageResponseLocal,
/// so everything that changes the response is done here, the same way on every game, from what they all share (the
/// zombie's profile and the response itself, whose Random decides chances). Side effects only the server should do
/// (buffs, damage to the attacker, the Volatile's fuse) are done there alone.
/// </summary>
public static class ZedCombat
{
    private class PoiseState
    {
        public float Value;
        public float LastHit;
    }

    private static readonly Dictionary<int, PoiseState> poise = new Dictionary<int, PoiseState>();
    private static readonly FastTags<TagGroup.Global> MeleeTag = FastTags<TagGroup.Global>.Parse("melee");
    private static readonly FastTags<TagGroup.Global> ReachTag = FastTags<TagGroup.Global>.Parse("longShaft");
    private static readonly FastTags<TagGroup.Global> ShotgunTag = FastTags<TagGroup.Global>.Parse("shotgun");

    /// <summary>Our own staggers (a Sprinter out of breath, the Alpha falling): a 1-point internal hit of this type,
    /// which everything here leaves alone.</summary>
    public const EnumDamageTypes StaggerType = EnumDamageTypes.Sprain;

    public static void OnHit(EntityAlive victim, ref DamageResponse dr)
    {
        if (dr.Source == null || (dr.Source.GetSource() == EnumDamageSource.Internal && dr.Source.GetDamageType() == StaggerType))
        {
            return;
        }
        if (ZedStore.IsZombie(victim))
        {
            ZombieHit(victim, ref dr);
        }
        else if (victim is EntityPlayer)
        {
            PlayerHit(victim, ref dr);
        }
    }

    // ------------------------------------------------------------------ hits on zombies

    private static void ZombieHit(EntityAlive z, ref DamageResponse dr)
    {
        if (z.IsDead())
        {
            return;
        }
        ZedProfile p = ZedStore.Get(z.entityId);
        EnumDamageTypes type = dr.Source.GetDamageType();
        bool explosion = dr.HitDirection == Utils.EnumHitDirection.Explosion;
        bool blunt = type == EnumDamageTypes.Bashing || type == EnumDamageTypes.Crushing;
        bool heat = type == EnumDamageTypes.Heat;
        ItemClass item = dr.Source.ItemClass;
        bool melee = item != null && item.HasAnyTags(MeleeTag);
        bool shotgun = item != null && (item.HasAnyTags(ShotgunTag) || item.GetItemName().IndexOf("Shotgun", StringComparison.OrdinalIgnoreCase) >= 0);
        bool head = (dr.HitBodyPart & EnumBodyPartHit.Head) != 0;
        bool legs = (dr.HitBodyPart & EnumBodyPartHit.Legs) != 0;
        int original = dr.Strength;
        float s = original;
        bool absorbedHead = false;
        bool gearBroke = false;

        if (p != null)
        {
            if (heat)
            {
                if (p.Has(ZedMutation.Smoldering))
                {
                    s = 0f;
                }
                else if (p.Has(ZedMutation.Frostbitten) || p.Has(ZedMutation.Regenerator))
                {
                    s *= 1.5f;
                }
            }
            if (type == EnumDamageTypes.Cold && p.Has(ZedMutation.Frostbitten))
            {
                s = 0f;
            }
            if (head && p.Has(ZedMutation.Hulking))
            {
                s *= 1.5f;
            }
            if (blunt && p.Has(ZedMutation.Spiked))
            {
                s *= 1.5f;
            }
            s = Gear(p, dr, s, blunt, explosion, ref absorbedHead, ref gearBroke);
        }

        if (ZedSettings.HitLocations && melee && (z.IsWalkTypeACrawl() || z.bodyDamage.CurrentStun == EnumEntityStunType.Prone
            || z.bodyDamage.CurrentStun == EnumEntityStunType.Kneel))
        {
            // Downed: double from melee
            s *= 2f;
        }

        dr.Strength = Mathf.Max(0, Mathf.RoundToInt(s));
        bool fatalNow = z.Health - dr.Strength <= 0;
        if (dr.Strength < original)
        {
            dr.Fatal = dr.Fatal && fatalNow;
        }
        else if (dr.Strength > original)
        {
            dr.Fatal = dr.Fatal || fatalNow;
        }
        if (dr.Strength == 0)
        {
            dr.Fatal = false;
            dr.Dismember = false;
        }
        if (absorbedHead && head)
        {
            // The helmet took it: no decapitation
            dr.Dismember = false;
        }

        if (ZedSettings.HitLocations && dr.Strength > 0)
        {
            Locations(z, p, ref dr, blunt, shotgun, explosion, head, legs, type);
        }
        if (p != null && dr.Source.BuffClass == null)
        {
            // A hit gets a Possum lying "dead" up, even one its gear took whole; bleeding and burning ticks aren't hits
            ZedPossum.Hit(z, p, z.world.GetEntity(dr.Source.getEntityId()) as EntityAlive);
        }
        if (p != null && ZedPossum.FakeDeath(z, p, ref dr))
        {
            // A Possum drops as if dead instead (see ZedPossum)
        }
        else if (ZedSettings.Brutal && dr.Fatal && !head && !heat && !explosion && !z.IsWalkTypeACrawl() && p != null && p.Humanoid
            && dr.Random < 0.1f)
        {
            // Double tap: it goes down without dying and gets up 3 to 6 s later as a crawler
            int keep = Mathf.Max(1, z.GetMaxHealth() / 4);
            dr.Strength = Mathf.Max(0, z.Health - keep);
            dr.Fatal = false;
            dr.Dismember = false;
            dr.Stun = EnumEntityStunType.Prone;
            dr.StunDuration = 3f + 30f * dr.Random;
            dr.TurnIntoCrawler = true;
            dr.CrippleLegs = true;
        }

        if (gearBroke && ZedStore.IsServer)
        {
            ZedStore.GearOff(z, p);
            ZedStore.Changed(z);
        }
        else if (gearBroke && ZedStore.DrawsLooks)
        {
            ZedModels.Refresh(z, p);
        }
        if (ZedStore.IsServer && p != null && dr.Strength > 0)
        {
            ServerReactions(z, p, dr, original, type, heat, melee, head);
        }
    }

    /// <summary>Gear soaks its share of hits on what it covers until it breaks (blunt hits wear it 50% faster;
    /// armor-piercing rounds go straight through; an explosion strips it all). Every game keeps the same soak.</summary>
    private static float Gear(ZedProfile p, DamageResponse dr, float s, bool blunt, bool explosion, ref bool absorbedHead, ref bool broke)
    {
        if (p.Gear.Count == 0)
        {
            return s;
        }
        if (explosion)
        {
            foreach (ZedGearPiece g in p.Gear)
            {
                if (!g.Broken)
                {
                    g.Soak = 0f;
                    broke = true;
                }
            }
            return s;
        }
        string ammo = Ammo(dr.Source.AttackingItem);
        if (ammo.EndsWith("AP") || ammo.Contains("BulletAP"))
        {
            return s;
        }
        foreach (ZedGearPiece g in p.Gear)
        {
            if (g.Broken || s <= 0f || !ZedGearInfo.PartCovers(g.Kind, g.Part, dr.HitBodyPart, dr.HitDirection))
            {
                continue;
            }
            float takes = s * ZedGearInfo.All[g.Kind].Takes;
            float wear = takes * (blunt ? 1.5f : 1f);
            if (wear >= g.Soak)
            {
                takes *= g.Soak / wear;
                g.Soak = 0f;
                broke = true;
            }
            else
            {
                g.Soak -= wear;
            }
            s -= takes;
            if (ZedGearInfo.All[g.Kind].IsHelmet)
            {
                absorbedHead = true;
            }
        }
        return s;
    }

    /// <summary>The ammo a gun has loaded (the hit's item is the gun), or the item's own name.</summary>
    private static string Ammo(ItemValue iv)
    {
        ItemClass ic = iv?.ItemClass;
        if (ic == null)
        {
            return "";
        }
        if (ic.Actions != null && ic.Actions.Length > 0 && ic.Actions[0] is ItemActionAttack attack && attack.MagazineItemNames != null
            && iv.SelectedAmmoTypeIndex < attack.MagazineItemNames.Length)
        {
            return attack.MagazineItemNames[iv.SelectedAmmoTypeIndex] ?? "";
        }
        return ic.GetItemName() ?? "";
    }

    /// <summary>Poise, trips, dazes, a Hulking dropped by its legs, and blades severing on the kill.</summary>
    private static void Locations(EntityAlive z, ZedProfile p, ref DamageResponse dr, bool blunt, bool shotgun, bool explosion, bool head,
        bool legs, EnumDamageTypes type)
    {
        int max = Mathf.Max(1, z.GetMaxHealth());
        if (!dr.Fatal && dr.Stun == EnumEntityStunType.None)
        {
            bool big = p != null && (p.Has(ZedMutation.Hulking) || p.Champion || p.Alpha);
            if (big && p.Has(ZedMutation.Hulking) && dr.CrippleLegs)
            {
                dr.Stun = EnumEntityStunType.Prone;
                dr.StunDuration = 4f;
            }
            else if (Poise(z, max, big, dr.Strength * (blunt ? 1.6f : 1f) * (shotgun ? 1.4f : 1f) * (explosion ? 2f : 1f)))
            {
                dr.Stun = EnumEntityStunType.Stumble;
                dr.StunDuration = 1.2f;
            }
            else if (legs && ZedBrain.Running(z) && dr.Strength >= max * 0.15f && dr.Random < 0.5f && !big)
            {
                // A solid leg hit on a runner trips it
                dr.Stun = EnumEntityStunType.Stumble;
                dr.StunDuration = 1f;
            }
            else if (head && dr.Strength >= max * 0.25f && !big)
            {
                dr.Stun = EnumEntityStunType.Stumble;
                dr.StunDuration = 0.6f;
            }
        }
        if (dr.Fatal && type == EnumDamageTypes.Slashing && dr.Random < 0.35f && (dr.HitBodyPart & (EnumBodyPartHit.Arms | EnumBodyPartHit.Head)) != 0)
        {
            // Blades sever more often on the killing blow
            dr.Dismember = true;
        }
    }

    /// <summary>True when this hit uses up the zombie's poise (then it's refilled). Poise is a third of its health
    /// (between 60 and 400, double for big zombies) and comes back 2 s after the last hit.</summary>
    private static bool Poise(EntityAlive z, int max, bool big, float drain)
    {
        float full = Mathf.Clamp(max * 0.35f, 60f, 400f) * (big ? 2f : 1f);
        if (!poise.TryGetValue(z.entityId, out PoiseState st))
        {
            st = new PoiseState { Value = full };
            poise[z.entityId] = st;
        }
        float now = Time.time;
        if (now - st.LastHit > 2f)
        {
            st.Value = Mathf.Min(full, st.Value + full * 0.25f * (now - st.LastHit - 2f));
        }
        st.LastHit = now;
        st.Value -= drain;
        if (st.Value <= 0f)
        {
            st.Value = full;
            return true;
        }
        return false;
    }

    public static void Forget(int entityId)
    {
        poise.Remove(entityId);
    }

    private static void ServerReactions(EntityAlive z, ZedProfile p, DamageResponse dr, int original, EnumDamageTypes type, bool heat,
        bool melee, bool head)
    {
        ZedBrain brain = ZedBrain.Of(z);
        if (brain != null)
        {
            brain.LastHit = Time.time;
            brain.Engaged = true;
            brain.Release();
        }
        if (p.Has(ZedMutation.Stalker) && !p.Revealed)
        {
            p.Revealed = true;
            ZedStore.Changed(z);
        }
        if (p.Has(ZedMutation.Volatile) && p.Tank == 0 && brain != null && brain.TankBlowAt < 0f)
        {
            bool chest = (dr.HitBodyPart & EnumBodyPartHit.Torso) != 0 && dr.HitDirection != Utils.EnumHitDirection.Back;
            if (chest)
            {
                brain.TankDamage += original;
            }
            if (heat || brain.TankDamage >= 60f)
            {
                brain.TankBlowAt = Time.time + 1.5f;
                Audio.Manager.BroadcastPlay(z, "hulkexplodewarning");
            }
        }
        EntityAlive attacker = z.world.GetEntity(dr.Source.getEntityId()) as EntityAlive;
        if (attacker is EntityPlayer && melee && !attacker.IsDead())
        {
            bool reach = dr.Source.ItemClass != null && dr.Source.ItemClass.HasAnyTags(ReachTag);
            if (p.Has(ZedMutation.Spiked) && !reach)
            {
                // Its spurs scratch whoever hits it up close
                attacker.DamageEntity(new DamageSource(EnumDamageSource.External, EnumDamageTypes.Piercing), 3, false);
                if (dr.Random > 0.8f)
                {
                    attacker.Buffs.AddBuff("buffInjuryBleedingOne", z.entityId);
                }
            }
            if (p.Has(ZedMutation.Toxic))
            {
                attacker.DamageEntity(new DamageSource(EnumDamageSource.External, EnumDamageTypes.Toxic), 3, false);
            }
        }
    }

    // ------------------------------------------------------------------ hits on players

    private static void PlayerHit(EntityAlive player, ref DamageResponse dr)
    {
        EntityAlive z = player.world.GetEntity(dr.Source.getEntityId()) as EntityAlive;
        if (z == null || !ZedStore.IsZombie(z) || dr.Strength <= 0)
        {
            return;
        }
        ZedProfile p = ZedStore.Get(z.entityId);
        int original = dr.Strength;
        float s = original;
        if (ZedSettings.HitLocations)
        {
            int arms = ArmsLost(z);
            s *= arms >= 2 ? 0.4f : arms == 1 ? 0.7f : 1f;
        }
        dr.Strength = Mathf.Max(0, Mathf.RoundToInt(s));
        if (dr.Strength < original)
        {
            dr.Fatal = dr.Fatal && player.Health - dr.Strength <= 0;
        }

        if (p != null && p.Has(ZedMutation.Hulking) && !player.isEntityRemote && player is EntityPlayerLocal)
        {
            // Knocked back about 1.5 m, on the player's own game (it moves its player)
            Vector3 away = player.position - z.position;
            away.y = 0f;
            player.motion += away.normalized * 0.55f + Vector3.up * 0.2f;
        }
        if (!ZedStore.IsServer || p == null || player.Buffs == null)
        {
            return;
        }
        ZedBrain brain = ZedBrain.Of(z);
        if (brain != null)
        {
            brain.Engaged = true;
        }
        if (p.Has(ZedMutation.Spiked) && dr.Random < 0.25f)
        {
            player.Buffs.AddBuff("buffInjuryBleedingOne", z.entityId);
        }
        if (p.Has(ZedMutation.Grabber) && dr.Random < 0.2f && !player.Buffs.HasBuff("buffZedGrabImmune") && !player.Buffs.HasBuff("buffZedGrabbed"))
        {
            ZedBrain.Of(z)?.Hold(player);
        }
        if (p.Has(ZedMutation.Toxic))
        {
            player.Buffs.AddBuff("buffZedPoisoned", z.entityId);
        }
        if (p.Has(ZedMutation.Frostbitten))
        {
            player.Buffs.AddBuff(player.Buffs.HasBuff("buffZedChilled1") ? "buffZedChilled2" : "buffZedChilled1", z.entityId);
        }
        if (p.Has(ZedMutation.Smoldering))
        {
            player.Buffs.AddBuff("buffBurningElement", z.entityId);
        }
    }

    /// <summary>How many arms a zombie has lost (0, 1 or 2).</summary>
    public static int ArmsLost(EntityAlive z)
    {
        uint f = z.bodyDamage.Flags;
        int n = 0;
        if ((f & (BodyDamage.cNoArmLUpper | BodyDamage.cNoArmLLower)) != 0)
        {
            n++;
        }
        if ((f & (BodyDamage.cNoArmRUpper | BodyDamage.cNoArmRLower)) != 0)
        {
            n++;
        }
        return n;
    }

    /// <summary>Server: makes a zombie stumble, kneel or fall for `seconds`, the same on every game (sent as a 1-point
    /// hit carrying the stun).</summary>
    public static void Stagger(EntityAlive z, EnumEntityStunType stun, float seconds)
    {
        if (!ZedStore.IsServer || z == null || z.IsDead())
        {
            return;
        }
        DamageResponse dr = DamageResponse.New(new DamageSource(EnumDamageSource.Internal, StaggerType), false);
        dr.Strength = 1;
        dr.Stun = stun;
        dr.StunDuration = seconds;
        dr.HitBodyPart = EnumBodyPartHit.Torso;
        dr.HitDirection = Utils.EnumHitDirection.Front;
        z.ProcessDamageResponse(dr);
    }
}

/// <summary>Runs ZedCombat on every hit, once, before the game applies it (the zombie and player classes override
/// the method and call the base one: only the outermost call counts).</summary>
[HarmonyPatch]
public class ZedHitPatch
{
    [ThreadStatic] private static int depth;

    public static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Method(typeof(EntityAlive), nameof(EntityAlive.ProcessDamageResponseLocal));
        foreach (Type t in new[] { typeof(EntityHuman), typeof(EntityZombieCop), typeof(EntityPlayerLocal) })
        {
            MethodInfo m = AccessTools.DeclaredMethod(t, nameof(EntityAlive.ProcessDamageResponseLocal));
            if (m != null)
            {
                yield return m;
            }
        }
    }

    public static void Prefix(EntityAlive __instance, ref DamageResponse _dmResponse)
    {
        if (depth++ > 0)
        {
            return;
        }
        try
        {
            ZedCombat.OnHit(__instance, ref _dmResponse);
        }
        catch (Exception e)
        {
            Log.Exception(e);
        }
    }

    public static Exception Finalizer(Exception __exception)
    {
        depth = Math.Max(0, depth - 1);
        return __exception;
    }
}

/// <summary>Block damage: a zombie missing arms hits blocks softer; on Brutal, zombies piled against blocks hit harder.</summary>
[HarmonyPatch(typeof(EntityAlive), nameof(EntityAlive.GetBlockDamageScale))]
public class ZedBlockDamagePatch
{
    public static void Postfix(EntityAlive __instance, ref float __result)
    {
        if (!ZedStore.IsZombie(__instance))
        {
            return;
        }
        if (ZedSettings.HitLocations)
        {
            int arms = ZedCombat.ArmsLost(__instance);
            __result *= arms >= 2 ? 0.25f : arms == 1 ? 0.7f : 1f;
        }
        if (ZedSettings.Brutal)
        {
            int crowd = 0;
            foreach (EntityAlive e in __instance.world.EntityAlives)
            {
                if (e != __instance && e.IsBreakingBlocks && !e.IsDead() && (e.position - __instance.position).sqrMagnitude < 2.25f)
                {
                    crowd++;
                }
            }
            __result *= 1f + Mathf.Min(0.6f, 0.15f * crowd);
        }
    }
}
