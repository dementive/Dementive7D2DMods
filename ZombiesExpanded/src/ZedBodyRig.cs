using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// A zombie's body: its skeleton reshaped once (gaunt, bulky, bloated) by scaling bones, which the animator never
/// touches, and posture offsets (hunched, a sluggish droop and sway, a relentless forward lean) added on top of the
/// animation every frame. Runs on every game, so the bones' hit boxes match wherever a hit is worked out. Needs the
/// standard zombie skeleton's bone names; a zombie without them keeps its shape.
/// </summary>
public class ZedBodyRig : MonoBehaviour
{
    private EntityAlive zombie;
    private readonly List<Transform> poseBones = new List<Transform>();
    private readonly List<Quaternion> poseOffsets = new List<Quaternion>();
    private readonly List<Quaternion> lastPosed = new List<Quaternion>();
    private Transform swayBone;
    private Quaternion lastSway;
    private float swayPhase;

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
                // A broad chest that pushes the shoulders out, thick arms of the usual length
                ScaleKeep(root, "Spine2", new Vector3(1.15f, 1.04f, 1.12f), "Neck");
                Scale(root, "LeftShoulder", new Vector3(1f / 1.15f, 1f, 1f));
                Scale(root, "RightShoulder", new Vector3(1f / 1.15f, 1f, 1f));
                Scale(root, "LeftArm", new Vector3(1f, 1.22f, 1.22f));
                Scale(root, "RightArm", new Vector3(1f, 1.22f, 1.22f));
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
                    // Hands grown too big
                    Scale(root, "LeftHand", new Vector3(1.35f, 1.12f, 1.12f));
                    Scale(root, "RightHand", new Vector3(1.35f, 1.12f, 1.12f));
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
    }
}
