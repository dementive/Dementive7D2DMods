using UnityEngine;

/// <summary>
/// An old injury's pose, added on top of the animation every frame after the body's posture (ZedBodyRig): a limp arm
/// hanging dead at the side, a dragged foot turned in on a stiff leg, a lolled head or a twisted back. The arm and the
/// leg are aimed in the world from where the bones are, whatever their axes, so they hang and scuff the same over any
/// posture; the head and the back turn on the bones' own axes, like the body's posture. Never touches Spine2 (the
/// sluggish sway's). Only Unity, so the editor preview (unity/Assets/Editor/InjuryPreview.cs) runs this same code
/// from the built DLL. A skeleton without the bones an injury needs doesn't show it.
/// </summary>
public class ZedInjuryPose
{
    // Limp arm: how much of the animation's swing it takes out (walking, and attacking so the swing still shows), the
    // shoulder's sag, and how the arm hangs: a little forward, the elbow bent a little
    private const float Hold = 0.85f;
    private const float AttackHold = 0.45f;
    private const float Sag = 6f;
    private const float Forward = 4f;
    private const float Elbow = 12f;
    // Dragged foot: the hip and the foot turned in, the sole rolled in, the most of the knee's bend taken out, and
    // the ankle's height off the ground (a share of the leg's length) that the stiff knee never pushes it below
    private const float HipTurn = 5f;
    private const float FootTurn = 14f;
    private const float FootRoll = 10f;
    private const float Stiff = 0.6f;
    private const float AnkleHeight = 0.15f;

    private readonly ZedInjury injury;
    /// <summary>1 on the left, -1 on the right.</summary>
    private readonly float side;
    private readonly float abduct;
    private readonly Transform root;
    private readonly Transform hips;
    private readonly Transform neck;
    private readonly Transform otherArm;
    /// <summary>The limp arm's hand, the dragged foot's toes.</summary>
    private readonly Transform end;
    /// <summary>The bones it turns, down the limb (the arm: shoulder, upper arm, forearm; the leg: thigh, shin,
    /// foot), or the neck and head, or the low and high back.</summary>
    private readonly Transform[] bones;
    private readonly Quaternion[] offsets;
    private readonly Quaternion[] last;
    private readonly bool valid;

    /// <summary>The injury's pose for the skeleton under `root`, or null if the skeleton lacks the bones. `seed`
    /// varies how far the head lolls and the back twists; `abduct` is how far out from the body a limp arm hangs, in
    /// degrees.</summary>
    public static ZedInjuryPose Create(Transform root, ZedInjury injury, bool left, int seed, float abduct)
    {
        ZedInjuryPose pose = new ZedInjuryPose(root, injury, left, seed, abduct);
        return pose.valid ? pose : null;
    }

    private ZedInjuryPose(Transform root, ZedInjury injury, bool left, int seed, float abduct)
    {
        this.injury = injury;
        this.root = root;
        this.abduct = abduct;
        side = left ? 1f : -1f;
        string near = left ? "Left" : "Right";
        float roll1 = ((seed >> 8) & 0xff) / 255f;
        float roll2 = ((seed >> 16) & 0xff) / 255f;
        switch (injury)
        {
            case ZedInjury.LimpArm:
                hips = Find(root, "Hips");
                neck = Find(root, "Neck");
                otherArm = Find(root, left ? "RightArm" : "LeftArm");
                end = Find(root, near + "Hand");
                bones = new[] { Find(root, near + "Shoulder"), Find(root, near + "Arm"), Find(root, near + "ForeArm") };
                valid = hips != null && neck != null && otherArm != null && end != null && bones[1] != null && bones[2] != null;
                break;
            case ZedInjury.DraggedFoot:
                end = Find(root, near + "ToeBase");
                bones = new[] { Find(root, near + "UpLeg"), Find(root, near + "Leg"), Find(root, near + "Foot") };
                valid = bones[0] != null && bones[1] != null && bones[2] != null;
                break;
            case ZedInjury.LolledHead:
                // 25 to 35 degrees to the side and 10 forward, two parts in five at the neck, the rest at the skull
                bones = new[] { Find(root, "Neck"), Find(root, "Head") };
                offsets = Split(Quaternion.Euler(10f, 0f, side * (25f + 10f * roll1)), 0.4f);
                break;
            case ZedInjury.TwistedBack:
                // Twisted 10 to 15 degrees (the shoulder on its side brought forward) and leaning 6 to 9 to that side,
                // half low in the back and half high
                bones = new[] { Find(root, "Spine1"), Find(root, "Spine3") };
                offsets = Split(Quaternion.Euler(0f, side * (10f + 5f * roll1), side * (6f + 3f * roll2)), 0.5f);
                break;
            default:
                bones = new Transform[0];
                break;
        }
        if (offsets != null)
        {
            valid = bones[0] != null || bones[1] != null;
        }
        last = new Quaternion[bones.Length];
    }

    /// <summary>Shares `total` out between the two bones, the first taking `first` of it; a bone the skeleton lacks
    /// leaves it all to the other.</summary>
    private Quaternion[] Split(Quaternion total, float first)
    {
        if (bones[0] == null || bones[1] == null)
        {
            return new[] { total, total };
        }
        return new[] { Quaternion.Slerp(Quaternion.identity, total, first), Quaternion.Slerp(Quaternion.identity, total, 1f - first) };
    }

    /// <summary>The first transform named `name` under `parent`, searched like the game's GameUtils.FindDeepChild.</summary>
    private static Transform Find(Transform parent, string name)
    {
        Transform t = parent.Find(name);
        if (t != null)
        {
            return t;
        }
        for (int i = 0; i < parent.childCount; i++)
        {
            t = Find(parent.GetChild(i), name);
            if (t != null)
            {
                return t;
            }
        }
        return null;
    }

    /// <summary>Poses the bones the animator just wrote (one it skipped, off screen, still holds last frame's pose).
    /// `weight` eases the injury in and out (0 while the zombie lies down or crawls), `attacking` (0 to 1) lets a limp
    /// arm keep more of an attack's swing, and `ground` is the height of the ground under the zombie, in the world.</summary>
    public void Apply(float weight, float attacking, float ground)
    {
        switch (injury)
        {
            case ZedInjury.LimpArm:
                LimpArm(weight * Mathf.Lerp(Hold, AttackHold, attacking));
                break;
            case ZedInjury.DraggedFoot:
                DraggedFoot(weight, ground);
                break;
            default:
                for (int i = 0; i < bones.Length; i++)
                {
                    if (Fresh(i))
                    {
                        bones[i].localRotation *= Quaternion.Slerp(Quaternion.identity, offsets[i], weight);
                        last[i] = bones[i].localRotation;
                    }
                }
                break;
        }
    }

    private bool Fresh(int i)
    {
        return bones[i] != null && bones[i].localRotation != last[i];
    }

    private void LimpArm(float pull)
    {
        Transform shoulder = bones[0], arm = bones[1], foreArm = bones[2];
        // The body's frame from where its bones are: up the spine, across the shoulders
        Vector3 up = (neck.position - hips.position).normalized;
        Vector3 right = (side * (otherArm.position - arm.position)).normalized;
        Vector3 forward = Vector3.Cross(right, up).normalized;
        Vector3 outward = -side * right;
        if (Fresh(0))
        {
            // The shoulder sags
            shoulder.rotation = Quaternion.AngleAxis(side * Sag * pull, forward) * shoulder.rotation;
            last[0] = shoulder.localRotation;
        }
        // Down along the body, pulled halfway to straight down while it stands, then out to the side to clear the body
        // and a little forward
        Vector3 down = Vector3.Slerp(-up, Vector3.down, 0.5f * Mathf.Clamp01((Vector3.Dot(up, Vector3.up) - 0.3f) / 0.5f));
        Vector3 hang = (down + Vector3.ProjectOnPlane(outward, down).normalized * Mathf.Tan(abduct * Mathf.Deg2Rad)
            + Vector3.ProjectOnPlane(forward, down).normalized * Mathf.Tan(Forward * Mathf.Deg2Rad)).normalized;
        if (Fresh(1))
        {
            Aim(arm, foreArm.position, hang, pull);
            last[1] = arm.localRotation;
        }
        if (Fresh(2))
        {
            // Nearly straight at the elbow, bent a little forward
            Vector3 upper = (foreArm.position - arm.position).normalized;
            Aim(foreArm, end.position, Vector3.RotateTowards(upper, forward, Elbow * Mathf.Deg2Rad, 0f), pull);
            last[2] = foreArm.localRotation;
        }
    }

    /// <summary>Turns `bone` so its direction to `tip` moves `pull` of the way to `to`.</summary>
    private static void Aim(Transform bone, Vector3 tip, Vector3 to, float pull)
    {
        Vector3 now = tip - bone.position;
        if (now.sqrMagnitude < 1e-8f)
        {
            return;
        }
        bone.rotation = Quaternion.FromToRotation(now, Vector3.Slerp(now.normalized, to, pull)) * bone.rotation;
    }

    private void DraggedFoot(float weight, float ground)
    {
        Transform upLeg = bones[0], leg = bones[1], foot = bones[2];
        if (Fresh(0))
        {
            // The hip turned in
            Vector3 thighUp = upLeg.position - leg.position;
            if (thighUp.sqrMagnitude > 1e-8f)
            {
                upLeg.rotation = Quaternion.AngleAxis(side * HipTurn * weight, thighUp.normalized) * upLeg.rotation;
            }
            last[0] = upLeg.localRotation;
        }
        if (Fresh(1))
        {
            // The knee kept stiff: the shin turned toward the line of the thigh while that brings the foot down, and
            // only as far as it stays off the ground. So the foot drops and scuffs as it swings through, without
            // kicking out in front, and a foot on the ground (standing, crouched, kneeling) is left alone
            Vector3 knee = leg.position;
            Vector3 shin = foot.position - knee;
            Vector3 thigh = knee - upLeg.position;
            Vector3 axis = Vector3.Cross(shin, thigh);
            float floor = ground + AnkleHeight * (thigh.magnitude + shin.magnitude);
            if (foot.position.y > floor && axis.sqrMagnitude > 1e-10f)
            {
                float low = 0f, high = Stiff * weight * Vector3.Angle(shin, thigh);
                // Where on that turn the foot is lowest (its height along the turn has one low point)
                for (int i = 0; i < 12; i++)
                {
                    float a = low + (high - low) / 3f, b = high - (high - low) / 3f;
                    if (AnkleY(knee, shin, axis, a) < AnkleY(knee, shin, axis, b))
                    {
                        high = b;
                    }
                    else
                    {
                        low = a;
                    }
                }
                float angle = (low + high) * 0.5f;
                if (AnkleY(knee, shin, axis, angle) < floor)
                {
                    // Down to the ground and no further
                    low = 0f;
                    high = angle;
                    for (int i = 0; i < 8; i++)
                    {
                        float mid = (low + high) * 0.5f;
                        if (AnkleY(knee, shin, axis, mid) < floor)
                        {
                            high = mid;
                        }
                        else
                        {
                            low = mid;
                        }
                    }
                    angle = low;
                }
                leg.rotation = Quaternion.AngleAxis(angle, axis) * leg.rotation;
            }
            last[1] = leg.localRotation;
        }
        if (Fresh(2))
        {
            // The toes turned in, and the sole rolled in about them so its outer edge scuffs
            Vector3 toes = end != null ? end.position - foot.position : root.forward;
            if (toes.sqrMagnitude > 1e-8f)
            {
                Quaternion turn = Quaternion.AngleAxis(side * FootTurn * weight, Vector3.up);
                foot.rotation = Quaternion.AngleAxis(side * FootRoll * weight, turn * toes) * turn * foot.rotation;
            }
            last[2] = foot.localRotation;
        }
    }

    /// <summary>The ankle's height with the shin turned `angle` degrees about `axis` at the knee.</summary>
    private static float AnkleY(Vector3 knee, Vector3 shin, Vector3 axis, float angle)
    {
        return knee.y + (Quaternion.AngleAxis(angle, axis) * shin).y;
    }
}
