// Usage: Api.exe <managedDir> <harmonyDir> <TypeMetadataName|?search> ...
// Prints C# signatures of the declared members of game types, read via Roslyn (no runtime type loading).
// "?text" lists type names containing text.
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;

class Api
{
    // Folder with the Microsoft.CodeAnalysis DLLs; Scripts\build.bat sets ROSLYN_DIR to the one it compiled with
    static readonly string Roslyn = Environment.GetEnvironmentVariable("ROSLYN_DIR")
        ?? @"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\Roslyn";

    static void Main(string[] args)
    {
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            string p = Path.Combine(Roslyn, new AssemblyName(e.Name).Name + ".dll");
            return File.Exists(p) ? Assembly.LoadFrom(p) : null;
        };
        Run(args);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static void Run(string[] args)
    {
        var refs = Directory.GetFiles(args[0], "*.dll").Concat(Directory.GetFiles(args[1], "*.dll"))
            .Select(f => { try { return Microsoft.CodeAnalysis.MetadataReference.CreateFromFile(f); } catch { return null; } })
            .Where(r => r != null);
        var comp = Microsoft.CodeAnalysis.CSharp.CSharpCompilation.Create("x", references: refs);
        var asm = comp.References.Select(r => comp.GetAssemblyOrModuleSymbol(r)).OfType<Microsoft.CodeAnalysis.IAssemblySymbol>()
            .First(a => a.Name == "Assembly-CSharp");
        var fmt = Microsoft.CodeAnalysis.SymbolDisplayFormat.CSharpErrorMessageFormat
            .WithMemberOptions(Microsoft.CodeAnalysis.SymbolDisplayMemberOptions.IncludeAccessibility
                | Microsoft.CodeAnalysis.SymbolDisplayMemberOptions.IncludeModifiers
                | Microsoft.CodeAnalysis.SymbolDisplayMemberOptions.IncludeType
                | Microsoft.CodeAnalysis.SymbolDisplayMemberOptions.IncludeParameters
                | Microsoft.CodeAnalysis.SymbolDisplayMemberOptions.IncludeRef)
            .WithParameterOptions(Microsoft.CodeAnalysis.SymbolDisplayParameterOptions.IncludeType
                | Microsoft.CodeAnalysis.SymbolDisplayParameterOptions.IncludeName
                | Microsoft.CodeAnalysis.SymbolDisplayParameterOptions.IncludeDefaultValue
                | Microsoft.CodeAnalysis.SymbolDisplayParameterOptions.IncludeParamsRefOut);

        foreach (string a in args.Skip(2))
        {
            if (a.StartsWith("?"))
            {
                foreach (var t in All(asm.GlobalNamespace).Where(t => t.ToDisplayString().IndexOf(a.Substring(1), StringComparison.OrdinalIgnoreCase) >= 0))
                    Console.WriteLine("  " + t.ToDisplayString());
                continue;
            }
            var type = asm.GetTypeByMetadataName(a);
            if (type == null) { Console.WriteLine("### " + a + " NOT FOUND"); continue; }
            Console.WriteLine("### " + type.DeclaredAccessibility.ToString().ToLower() + " " + type.TypeKind.ToString().ToLower() + " " + type.ToDisplayString() + " : " + type.BaseType?.ToDisplayString());
            foreach (var m in type.GetMembers().Where(m => !m.IsImplicitlyDeclared))
            {
                if (m is Microsoft.CodeAnalysis.IMethodSymbol ms && (ms.MethodKind == Microsoft.CodeAnalysis.MethodKind.PropertyGet || ms.MethodKind == Microsoft.CodeAnalysis.MethodKind.PropertySet)) continue;
                Console.WriteLine("  " + m.ToDisplayString(fmt));
            }
        }
    }

    static System.Collections.Generic.IEnumerable<Microsoft.CodeAnalysis.INamedTypeSymbol> All(Microsoft.CodeAnalysis.INamespaceSymbol ns)
    {
        foreach (var t in ns.GetTypeMembers()) { yield return t; foreach (var n in t.GetTypeMembers()) yield return n; }
        foreach (var c in ns.GetNamespaceMembers()) foreach (var t in All(c)) yield return t;
    }
}
