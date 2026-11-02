using System;
using System.IO;

/// <summary>
/// A file Traps Expanded keeps in the current world's save folder on the server (TrapsExpanded/&lt;name&gt;): the
/// traps' kills, levels, upgrades and loaded ammo, and the Blood Moon records.
/// </summary>
public class TrapSaveFileDEM
{
    private readonly string name;
    private string loadedFrom;

    public TrapSaveFileDEM(string name)
    {
        this.name = name;
    }

    private static string Folder()
    {
        try
        {
            return Path.Combine(GameIO.GetSaveGameDir(), "TrapsExpanded");
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>The world closed: load again next time, even if the next world has the same save folder.</summary>
    public void Reset()
    {
        loadedFrom = null;
    }

    /// <summary>True when the world changed since the last load (or nothing was loaded yet).</summary>
    public bool NeedsLoad()
    {
        return Folder() != loadedFrom;
    }

    public void Load(Action<PooledBinaryReader> read)
    {
        string folder = Folder();
        loadedFrom = folder;
        if (folder == null)
        {
            return;
        }
        string path = Path.Combine(folder, name);
        if (!File.Exists(path))
        {
            return;
        }
        try
        {
            using (FileStream stream = File.OpenRead(path))
            {
                var reader = new PooledBinaryReader();
                reader.SetBaseStream(stream);
                read(reader);
            }
        }
        catch (Exception e)
        {
            Log.Warning($"TrapsExpanded: couldn't read {path}: {e.Message}");
        }
    }

    public void Save(Action<PooledBinaryWriter> write)
    {
        string folder = Folder();
        if (folder == null)
        {
            return;
        }
        try
        {
            Directory.CreateDirectory(folder);
            string path = Path.Combine(folder, name);
            string temp = path + ".tmp";
            using (FileStream stream = File.Create(temp))
            {
                var writer = new PooledBinaryWriter();
                writer.SetBaseStream(stream);
                write(writer);
                writer.Flush();
            }
            if (File.Exists(path))
            {
                File.Delete(path);
            }
            File.Move(temp, path);
        }
        catch (Exception e)
        {
            Log.Warning($"TrapsExpanded: couldn't save {name}: {e.Message}");
        }
    }
}
