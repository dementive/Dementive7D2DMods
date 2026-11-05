using UnityEngine;

/// <summary>
/// A model part that hangs (a gut loop, dog tags, a cut rope end, a torn length of chain): it swings about its pivot
/// as the zombie moves, lagging behind and settling under its own weight, never more than 35 degrees off the way it
/// hangs at rest, so it stays clear of the body. A look only, on each player's game; it rests when off screen or far.
/// </summary>
public class ZedSwing : MonoBehaviour
{
    private const float MaxAngle = 35f;
    private const float Damping = 0.94f;    // speed kept per 1/60 s
    private const float Far = 40f;

    private Quaternion rest;    // its local rotation as built
    private Vector3 hang;       // the way it hangs, in its own space: from the pivot to the middle of its mesh
    private float length;       // pivot to its far end, in its own units
    private Vector3 bob, lastBob;   // the far end, in world coordinates (so the floating origin doesn't move it)
    private bool swinging;
    private Renderer view;

    private void Awake()
    {
        rest = transform.localRotation;
        view = GetComponent<Renderer>();
        MeshFilter mf = GetComponent<MeshFilter>();
        Bounds b = mf != null && mf.sharedMesh != null ? mf.sharedMesh.bounds : new Bounds(Vector3.down * 0.1f, Vector3.one * 0.1f);
        hang = b.center.sqrMagnitude > 1e-8f ? b.center.normalized : Vector3.down;
        length = Mathf.Max(0.05f, b.center.magnitude * 2f);
    }

    private void LateUpdate()
    {
        Transform parent = transform.parent;
        Camera cam = Camera.main;
        if (parent == null || view == null || !view.isVisible || cam == null
            || (cam.transform.position - transform.position).sqrMagnitude > Far * Far)
        {
            if (swinging)
            {
                transform.localRotation = rest;
                swinging = false;
            }
            return;
        }
        Quaternion restWorld = parent.rotation * rest;
        Vector3 restDir = restWorld * hang;
        Vector3 pivot = transform.position + Origin.position;
        float len = length * transform.lossyScale.x;
        float dt = Mathf.Clamp(Time.deltaTime, 0.001f, 0.05f);
        if (!swinging)
        {
            bob = lastBob = pivot + restDir * len;
            swinging = true;
        }
        // Verlet: it keeps going the way it was going, slowing, and falls
        Vector3 velocity = (bob - lastBob) * Mathf.Pow(Damping, dt * 60f);
        lastBob = bob;
        bob += velocity + Physics.gravity * (dt * dt);
        // On its string, and never far from how it hangs at rest
        Vector3 dir = bob - pivot;
        dir = dir.sqrMagnitude > 1e-8f ? dir.normalized : restDir;
        float angle = Vector3.Angle(restDir, dir);
        if (angle > MaxAngle)
        {
            dir = Vector3.Slerp(restDir, dir, MaxAngle / angle);
        }
        bob = pivot + dir * len;
        transform.rotation = Quaternion.FromToRotation(restDir, dir) * restWorld;
    }
}

/// <summary>
/// A showpiece dragged along the ground behind a zombie: the cinder block chained to its ankle. The block trails the
/// shackle on its chain, sits on the ground under it, turns toward the zombie as it's pulled and scrapes while it
/// moves; the chain runs from the shackle to the block. The parts' rotations come in the zombie model's own space
/// (facing +Z, up +Y; see ZombiesModels.MakePrefab), so the block stands the way it was built wherever it lies. A look
/// only: every player's game places its own.
/// </summary>
public class ZedDrag : MonoBehaviour
{
    private const float Reach = 0.95f;      // how far the block trails behind the shackle
    private const float Lift = 0.1f;        // the block's pivot above its bottom face (see REMNANTS.md)
    private const float ChainBuilt = 1f;    // the chain's length as built

    private EntityAlive zombie;
    private Transform anchorBone;
    private Vector3 anchorLocal;
    private Transform chain, block;
    private Quaternion chainModel = Quaternion.identity, blockModel = Quaternion.identity;
    private Vector3 chainScale = Vector3.one;
    private int chainAxis = 2;
    private Vector3 blockAt;    // world coordinates
    private float ground;
    private float groundTimer;
    private bool placed;
    private AudioSource scrape;
    private static AudioClip scrapeClip;

    /// <summary>Takes a model's "...Drag" part off the bone it was built on and drags it instead.</summary>
    public static GameObject Add(EntityAlive zombie, Transform bone, Transform piece)
    {
        ZedDrag d = zombie.GetComponent<ZedDrag>();
        if (d == null)
        {
            d = zombie.gameObject.AddComponent<ZedDrag>();
            d.zombie = zombie;
        }
        GameObject go = Instantiate(piece.gameObject);
        go.name = "ZedDrag " + piece.name;
        ZedGameShader.Apply(go.transform);
        d.anchorBone = bone;
        if (piece.name.EndsWith("ChainDrag"))
        {
            d.chain = go.transform;
            d.chainModel = piece.localRotation;
            d.chainScale = piece.localScale;
            d.anchorLocal = piece.localPosition;
            // The chain runs from the shackle straight back (model -Z): that's the axis it stretches along
            Vector3 along = Quaternion.Inverse(d.chainModel) * Vector3.back;
            Vector3 a = new Vector3(Mathf.Abs(along.x), Mathf.Abs(along.y), Mathf.Abs(along.z));
            d.chainAxis = a.x >= a.y && a.x >= a.z ? 0 : a.y >= a.z ? 1 : 2;
        }
        else
        {
            d.block = go.transform;
            d.blockModel = piece.localRotation;
            d.Scrape(go);
        }
        return go;
    }

    private void Scrape(GameObject host)
    {
        scrape = host.AddComponent<AudioSource>();
        scrape.clip = ScrapeClip();
        scrape.loop = true;
        scrape.playOnAwake = false;
        scrape.spatialBlend = 1f;
        scrape.rolloffMode = AudioRolloffMode.Linear;
        scrape.minDistance = 1.5f;
        scrape.maxDistance = 22f;
        scrape.dopplerLevel = 0f;
        scrape.volume = 0f;
        scrape.Play();
    }

    /// <summary>Two seconds of concrete grinding on the ground: a low rumble, a rasp and ticks of grit, looping.</summary>
    private static AudioClip ScrapeClip()
    {
        if (scrapeClip != null)
        {
            return scrapeClip;
        }
        const int rate = 22050, n = rate * 2;
        float[] data = new float[n];
        System.Random r = new System.Random(7);
        float low = 0f, band = 0f, grit = 0f;
        for (int i = 0; i < n; i++)
        {
            float white = (float)r.NextDouble() * 2f - 1f;
            low += (white - low) * 0.06f;
            band += (white - band) * 0.3f;
            if (r.NextDouble() < 0.0012)
            {
                grit = 1f;
            }
            grit *= 0.992f;
            float t = (float)i / n;
            float judder = 0.7f + 0.3f * Mathf.Sin(t * Mathf.PI * 2f * 9f);
            data[i] = Mathf.Clamp((band - low) * 0.7f + low * 1.6f + white * grit * 0.45f, -1f, 1f) * judder * 0.8f;
        }
        scrapeClip = AudioClip.Create("ZedScrape", n, 1, rate, false);
        scrapeClip.SetData(data, 0);
        return scrapeClip;
    }

    private void LateUpdate()
    {
        if (anchorBone == null || block == null || zombie == null)
        {
            return;
        }
        float dt = Mathf.Max(Time.deltaTime, 0.001f);
        Vector3 origin = Origin.position;
        Vector3 a = anchorBone.TransformPoint(anchorLocal);
        if (!placed)
        {
            Vector3 back = -zombie.transform.forward;
            back.y = 0f;
            blockAt = a + origin + back.normalized * Reach;
            ground = Ground(blockAt, a.y + origin.y - 0.1f);
            blockAt.y = ground + Lift;
            placed = true;
        }
        Vector3 before = blockAt;
        Vector3 b = blockAt - origin;
        Vector3 flat = b - a;
        flat.y = 0f;
        float d = flat.magnitude;
        if (d > Reach)
        {
            b += -flat / d * (d - Reach);
        }
        blockAt = b + origin;
        groundTimer -= dt;
        if (groundTimer <= 0f || (blockAt - before).sqrMagnitude > 0.04f)
        {
            ground = Ground(blockAt, ground);
            groundTimer = 0.25f;
        }
        blockAt.y = Mathf.Lerp(blockAt.y, ground + Lift, 1f - Mathf.Exp(-12f * dt));
        b = blockAt - origin;

        Vector3 toward = a - b;
        toward.y = 0f;
        if (toward.sqrMagnitude > 1e-4f)
        {
            block.rotation = Quaternion.LookRotation(toward.normalized, Vector3.up) * blockModel;
        }
        block.position = b;

        if (chain != null)
        {
            Vector3 span = b - a;
            float len = span.magnitude;
            if (len > 0.01f)
            {
                chain.position = a;
                chain.rotation = Quaternion.LookRotation(-span / len, Vector3.up) * chainModel;
                Vector3 s = chainScale;
                s[chainAxis] *= len / ChainBuilt;
                chain.localScale = s;
            }
        }

        if (scrape != null)
        {
            Vector3 moved = blockAt - before;
            moved.y = 0f;
            float speed = moved.magnitude / dt;
            float target = Mathf.Clamp01(speed / 1.2f) * 0.55f;
            scrape.volume = Mathf.MoveTowards(scrape.volume, target, dt * 2.5f);
            scrape.pitch = 0.85f + 0.25f * Mathf.Clamp01(speed / 2f);
        }
    }

    /// <summary>The height of the ground (or floor) under a point, or `fallback` if there's none within reach.</summary>
    private float Ground(Vector3 world, float fallback)
    {
        World w = zombie.world;
        if (w != null && Voxel.Raycast(w, new Ray(world + Vector3.up * 1.2f, Vector3.down), 3f, false, false))
        {
            return Voxel.voxelRayHitInfo.hit.pos.y;
        }
        return fallback;
    }

    private void OnDestroy()
    {
        if (chain != null)
        {
            Destroy(chain.gameObject);
        }
        if (block != null)
        {
            Destroy(block.gameObject);
        }
    }
}

/// <summary>
/// Small signs of (un)life near the player, on each player's game: flies buzzing round the rotten ones (you hear the
/// swarm before you see it), breath clouding in the cold, and blood and drool flung from the jaw as they attack.
/// </summary>
public class ZedLife : MonoBehaviour
{
    private const float FlyRange = 18f;
    private const float Range = 25f;
    private const float Rotten = 0.85f;     // profile age past which the flies come

    private EntityAlive zombie;
    private ZedProfile profile;
    private Transform head, chest;
    private GameObject flies;
    private bool buzzing, wasAttacking;
    private float breathTimer;

    private static float coldChecked = -100f;
    private static bool coldOut;

    public static void Attach(EntityAlive zombie, ZedProfile p)
    {
        if (!ZedSettings.Looks || !p.Humanoid || zombie.GetComponent<ZedLife>() != null)
        {
            return;
        }
        ZedLife life = zombie.gameObject.AddComponent<ZedLife>();
        life.zombie = zombie;
        life.profile = p;
        Transform model = zombie.emodel.GetModelTransform() ?? zombie.transform;
        life.head = zombie.emodel.GetHeadTransform() ?? GameUtils.FindDeepChild(model, "Head");
        life.chest = GameUtils.FindDeepChild(model, "Spine2") ?? zombie.emodel.GetPelvisTransform();
        life.breathTimer = Random.Range(0.5f, 4f);
    }

    private void Update()
    {
        if (zombie == null)
        {
            return;
        }
        Camera cam = Camera.main;
        float dist = cam != null ? Vector3.Distance(cam.transform.position, transform.position) : 999f;
        Flies(dist);
        if (zombie.IsDead() || head == null || dist > Range)
        {
            wasAttacking = false;
            return;
        }
        Breath();
        Spatter();
    }

    private void Flies(float dist)
    {
        bool on = ZedSettings.Flies && profile.Age > Rotten && chest != null && dist < FlyRange;
        if (on && flies == null)
        {
            GameObject template = ZedAssets.Get<GameObject>("FlySwarm");
            if (template != null)
            {
                flies = Instantiate(template, chest, false);
                flies.transform.localPosition = Vector3.zero;
            }
        }
        else if (!on && flies != null)
        {
            Destroy(flies);
            flies = null;
        }
        if (on != buzzing)
        {
            buzzing = on;
            if (on)
            {
                Audio.Manager.Play(zombie, "flies_lp");
            }
            else
            {
                Audio.Manager.Stop(zombie.entityId, "flies_lp");
            }
        }
    }

    /// <summary>A puff of breath every few seconds when it's cold out (always in the snow).</summary>
    private void Breath()
    {
        if (!ZedSettings.Breath || !Cold())
        {
            return;
        }
        breathTimer -= Time.deltaTime;
        if (breathTimer > 0f)
        {
            return;
        }
        breathTimer = Random.Range(2.2f, 4.5f);
        Effect("BreathPuff", 2f);
    }

    /// <summary>Blood and drool flung from the jaw as an attack starts.</summary>
    private void Spatter()
    {
        AvatarController avatar = zombie.emodel?.avatarController;
        bool attacking = avatar != null && avatar.IsAnimationAttackPlaying();
        if (attacking && !wasAttacking && ZedSettings.Drool && Random.value < 0.6f)
        {
            Effect("JawSpatter", 1.5f);
        }
        wasAttacking = attacking;
    }

    private bool Cold()
    {
        if (profile.Biome == ZedBiome.Snow)
        {
            return true;
        }
        if (Time.time - coldChecked > 5f)
        {
            coldChecked = Time.time;
            coldOut = WeatherManager.Instance != null && WeatherManager.GetTemperature() < 40f;
        }
        return coldOut;
    }

    /// <summary>A one-off effect at the mouth, pointing the way the head faces.</summary>
    private void Effect(string name, float life)
    {
        GameObject template = ZedAssets.Get<GameObject>(name);
        if (template == null)
        {
            return;
        }
        // The mouth: below and in front of the head bone (whose axes are the model's on the standard skeleton)
        Vector3 mouth = head.TransformPoint(new Vector3(0f, -0.035f, 0.11f));
        Vector3 facing = Vector3.ProjectOnPlane(zombie.transform.forward, Vector3.up);
        if (facing.sqrMagnitude < 1e-4f)
        {
            facing = zombie.transform.forward;
        }
        GameObject fx = Instantiate(template, mouth, Quaternion.LookRotation(facing.normalized, Vector3.up));
        foreach (ParticleSystem ps in fx.GetComponentsInChildren<ParticleSystem>())
        {
            ps.Play();
        }
        Destroy(fx, life);
    }

    private void OnDestroy()
    {
        if (buzzing && zombie != null)
        {
            Audio.Manager.Stop(zombie.entityId, "flies_lp");
        }
        if (flies != null)
        {
            Destroy(flies);
        }
    }
}
