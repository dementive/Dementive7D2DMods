using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// A zombie's body: its skeleton reshaped once (gaunt, bulky, bloated) by scaling bones, which the animator never
/// touches, and posture offsets (hunched, a sluggish droop and sway, a relentless forward lean) added on top of the
/// animation every frame, then its old injury's pose (ZedInjuryPose). Runs on every game, so the bones' hit boxes
/// match wherever a hit is worked out. Needs the standard zombie skeleton's bone names; a zombie without them keeps its
/// shape.
/// </summary>
public class ZedBodyRig : MonoBehaviour
{
    /// <summary>The game's standing sleeper pose (sleeperIdle); the others sit or lie.</summary>
    private const int StandingSleeperPose = 5;

    private EntityAlive zombie;
    private readonly List<Transform> poseBones = new List<Transform>();
    private readonly List<Quaternion> poseOffsets = new List<Quaternion>();
    private readonly List<Quaternion> lastPosed = new List<Quaternion>();
    private Transform swayBone;
    private Quaternion lastSway;
    private float swayPhase;
    private ZedInjuryPose injury;
    /// <summary>A limp arm's dismemberment flags: once that arm is cut off, the pose goes with it.</summary>
    private uint injuryArm;
    private float injuryWeight = -1f;
    private float attacking;

    public static void Attach(EntityAlive zombie, ZedProfile p)
    {
        if (!p.Humanoid || zombie.GetComponent<ZedBodyRig>() != null)
        {
            return;
        }
        Transform root = zombie.emodel.GetModelTransform();
        if (root == null || GameUtils.FindDeepChild(root, "Spine2") == null)
        {
            return;
        }
        ZedBodyRig rig = zombie.gameObject.AddComponent<ZedBodyRig>();
        rig.zombie = zombie;
        rig.Shape(root, p);
        rig.Injure(root, p);
    }

    /// <summary>The old injury's pose, if the skeleton has its bones (never a limp arm that's already cut off).</summary>
    private void Injure(Transform root, ZedProfile p)
    {
        if (p.Injury == ZedInjury.None)
        {
            return;
        }
        if (p.Injury == ZedInjury.LimpArm)
        {
            injuryArm = p.InjuryLeft ? BodyDamage.cNoArmLUpper | BodyDamage.cNoArmLLower : BodyDamage.cNoArmRUpper | BodyDamage.cNoArmRLower;
            if ((zombie.bodyDamage.Flags & injuryArm) != 0)
            {
                return;
            }
        }
        injury = ZedInjuryPose.Create(root, p.Injury, p.InjuryLeft, p.Seed, LimpArmOut(p));
    }

    /// <summary>How far out from the body a limp arm hangs, in degrees: clear of the body, more for a broad chest or a
    /// swollen belly, and more again with something on that arm or hand (a cast, a chain, nails, spurs, a growth, big
    /// hands). The same on every game: it's all from the profile and the class's walk.</summary>
    private float LimpArmOut(ZedProfile p)
    {
        float angle = p.Body == ZedBody.Bloated ? 19f : p.Body == ZedBody.Bulky || zombie.GetWalkType() == EntityAlive.cWalkTypeFat ? 17f : 13f;
        ZedSlot used = ZedSlot.None;
        foreach (ZedRemnant r in p.Remnants)
        {
            if (ZedRemnantInfo.All.TryGetValue(r, out ZedRemnantInfo info))
            {
                used |= info.Slots;
            }
        }
        foreach (ZedMutation m in p.Mutations)
        {
            if (ZedMutationInfo.All.TryGetValue(m, out ZedMutationInfo info))
            {
                used |= info.Slots;
            }
        }
        ZedSlot arm = p.InjuryLeft ? ZedSlot.LeftArm | ZedSlot.LeftHand : ZedSlot.RightArm | ZedSlot.RightHand;
        return (used & arm) != 0 ? angle + 3f : angle;
    }

    private void Shape(Transform root, ZedProfile p)
    {
        switch (p.Body)
        {
            case ZedBody.Gaunt:
                // A narrow, flat torso (the neck and shoulders put back), thin arms and legs
                ScaleKeep(root, "Spine1", new Vector3(0.86f, 1f, 0.82f), "Neck", "LeftShoulder", "RightShoulder");
                Scale(root, "LeftArm", new Vector3(1f, 0.78f, 0.78f));
                Scale(root, "RightArm", new Vector3(1f, 0.78f, 0.78f));
                Scale(root, "LeftUpLeg", new Vector3(0.82f, 1f, 0.82f));
                Scale(root, "RightUpLeg", new Vector3(0.82f, 1f, 0.82f));
                break;
            case ZedBody.Bulky:
                // A broad chest that pushes the shoulders out. The shoulders take back their whole size, so none of the
                // chest's shape reaches the arms (it used to, and made the hands huge)
                ScaleKeep(root, "Spine2", new Vector3(1.15f, 1.04f, 1.12f), "Neck", "LeftShoulder", "RightShoulder");
                // Thick arms, scaled evenly: an arm scaled thicker but not longer skews the forearm and hand whenever
                // the elbow bends. The hands are put back to their own size
                ScaleKeep(root, "LeftArm", Vector3.one * 1.1f, "LeftHand");
                ScaleKeep(root, "RightArm", Vector3.one * 1.1f, "RightHand");
                break;
            case ZedBody.Bloated:
                // A swollen belly only
                ScaleKeep(root, "Spine", new Vector3(1.28f, 1f, 1.4f), "Spine2");
                break;
            case ZedBody.Hunched:
                Pose(root, "Spine3", Quaternion.Euler(18f, 0f, 0f));
                Pose(root, "Neck", Quaternion.Euler(-14f, 0f, 0f));
                break;
        }
        foreach (ZedMutation m in p.Mutations)
        {
            switch (m)
            {
                case ZedMutation.Grabber:
                    // Hands grown a little big, evenly (stretching them longer skewed the fingers as they curled); the
                    // gnarled hands model does the rest
                    Scale(root, "LeftHand", Vector3.one * 1.12f);
                    Scale(root, "RightHand", Vector3.one * 1.12f);
                    break;
                case ZedMutation.Leaper:
                    Pose(root, "Spine3", Quaternion.Euler(12f, 0f, 0f));
                    Pose(root, "Neck", Quaternion.Euler(-8f, 0f, 0f));
                    break;
                case ZedMutation.Screecher:
                    // Its jaw hangs open
                    Pose(root, "Jaw", Quaternion.Euler(20f, 0f, 0f));
                    break;
            }
        }
        switch (p.Temper)
        {
            case ZedTemper.Sluggish:
                Pose(root, "Neck", Quaternion.Euler(9f, 0f, 0f));
                swayBone = GameUtils.FindDeepChild(root, "Spine2");
                swayPhase = (p.Seed & 0xff) / 40f;
                break;
            case ZedTemper.Relentless:
                Pose(root, "Spine2", Quaternion.Euler(8f, 0f, 0f));
                break;
        }
    }

    private static void Scale(Transform root, string bone, Vector3 s)
    {
        Transform t = GameUtils.FindDeepChild(root, bone);
        if (t != null)
        {
            t.localScale = Vector3.Scale(t.localScale, s);
        }
    }

    /// <summary>Scales a bone and puts the given bones below it back to their own size, so only the part between
    /// them changes.</summary>
    private static void ScaleKeep(Transform root, string bone, Vector3 s, params string[] keep)
    {
        Transform t = GameUtils.FindDeepChild(root, bone);
        if (t == null)
        {
            return;
        }
        t.localScale = Vector3.Scale(t.localScale, s);
        Vector3 inverse = new Vector3(1f / s.x, 1f / s.y, 1f / s.z);
        foreach (string k in keep)
        {
            Transform c = GameUtils.FindDeepChild(t, k);
            if (c != null)
            {
                c.localScale = Vector3.Scale(c.localScale, inverse);
            }
        }
    }

    private void Pose(Transform root, string bone, Quaternion offset)
    {
        Transform t = GameUtils.FindDeepChild(root, bone);
        if (t == null)
        {
            return;
        }
        int i = poseBones.IndexOf(t);
        if (i >= 0)
        {
            poseOffsets[i] *= offset;
            return;
        }
        poseBones.Add(t);
        poseOffsets.Add(offset);
        lastPosed.Add(new Quaternion(0f, 0f, 0f, 0f));
    }

    private void LateUpdate()
    {
        if (zombie == null || zombie.emodel == null || zombie.emodel.IsRagdollActive || zombie.IsDead())
        {
            return;
        }
        for (int i = 0; i < poseBones.Count; i++)
        {
            Transform t = poseBones[i];
            if (t == null)
            {
                continue;
            }
            // Only on top of a pose the animator just wrote: when it skips a frame (off screen), adding again would
            // bend the bone further every frame
            if (t.localRotation == lastPosed[i])
            {
                continue;
            }
            t.localRotation *= poseOffsets[i];
            lastPosed[i] = t.localRotation;
        }
        if (swayBone != null && swayBone.localRotation != lastSway)
        {
            float sway = Mathf.Sin(Time.time * 2.4f + swayPhase) * 4f;
            swayBone.localRotation *= Quaternion.Euler(0f, 0f, sway);
            lastSway = swayBone.localRotation;
        }
        if (injury != null)
        {
            PoseInjury();
            // The injury may have turned the posture's bones further (the neck, the spine): what they hold now is
            // what this frame left on them
            for (int i = 0; i < poseBones.Count; i++)
            {
                if (poseBones[i] != null)
                {
                    lastPosed[i] = poseBones[i].localRotation;
                }
            }
        }
    }

    private void PoseInjury()
    {
        try
        {
            if (injuryArm != 0 && (zombie.bodyDamage.Flags & injuryArm) != 0)
            {
                // The limp arm was cut off
                injury = null;
                return;
            }
            // Eased out while it lies in a sleeper pose (asleep in a POI, a Possum playing dead; a standing sleeper
            // keeps it) or crawls, and back in as it gets up
            bool down = (zombie.IsSleeping && zombie.lastSleeperPose != StandingSleeperPose) || zombie.IsWalkTypeACrawl();
            float target = down ? 0f : 1f;
            injuryWeight = injuryWeight < 0f ? target : Mathf.MoveTowards(injuryWeight, target, Time.deltaTime * 2f);
            AvatarController avatar = zombie.emodel.avatarController;
            bool attack = avatar != null && avatar.IsAnimationAttackPlaying();
            attacking = Mathf.MoveTowards(attacking, attack ? 1f : 0f, Time.deltaTime * (attack ? 8f : 3f));
            if (injuryWeight > 0f)
            {
                injury.Apply(injuryWeight, attacking, transform.position.y);
            }
        }
        catch (System.Exception e)
        {
            // Another mod's zombie that doesn't work like the game's: no injury rather than an error every frame
            Log.Warning($"[ZombiesExpanded] Old injury pose off for {zombie.EntityClass?.entityClassName}: {e.Message}");
            injury = null;
        }
    }
}
