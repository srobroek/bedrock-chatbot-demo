import { awscdk, javascript } from "projen";
const project = new awscdk.AwsCdkTypeScriptApp({
  cdkVersion: "2.177.0",
  defaultReleaseBranch: "main",
  name: "cdk-helpdesk-chatbot",
  packageManager: javascript.NodePackageManager.PNPM,
  prettier: true,
  projenrcTs: true,
  gitignore:
      [
        ".Python",
        "[Bb]in",
        "[Ii]nclude",
        "[Ll]ib",
        "[Ll]ib64",
        "[Ll]ocal",
        "[Ss]cripts",
        "pyvenv.cfg",
        ".venv",
        "pip-selfcheck.json",
        ".idea/**/workspace.xml",
        ".idea/**/tasks.xml",
        ".idea/**/usage.statistics.xml",
        ".idea/**/dictionaries",
        ".idea/**/shelf",
        ".idea/**/aws.xml",
        ".idea/**/contentModel.xml",
        ".idea/**/dataSources/",
        ".idea/**/dataSources.ids",
        ".idea/**/dataSources.local.xml",
        ".idea/**/sqlDataSources.xml",
        ".idea/**/dynamic.xml",
        ".idea/**/uiDesigner.xml",
        ".idea/**/dbnavigator.xml",
        ".idea/**/gradle.xml",
        ".idea/**/libraries",
        "cmake-build-*/",
        ".idea/**/mongoSettings.xml",
        "*.iws",
        "out/",
        ".idea_modules/",
        "atlassian-ide-plugin.xml",
        ".idea/replstate.xml",
        ".idea/sonarlint/",
        "com_crashlytics_export_strings.xml",
        "crashlytics.properties",
        "crashlytics-build.properties",
        "fabric.properties",
        ".idea/httpRequests",
        ".idea/caches/build_file_checksums.ser",
        "__pycache__/",
        "*.py[cod]",
        "*$py.class",
        "*.so",
        "build/",
        "develop-eggs/",
        "dist/",
        "downloads/",
        "eggs/",
        ".eggs/",
        "lib/",
        "lib64/",
        "parts/",
        "sdist/",
        "var/",
        "wheels/",
        "share/python-wheels/",
        "*.egg-info/",
        ".installed.cfg",
        "*.egg",
        "MANIFEST",
        "*.manifest",
        "*.spec",
        "pip-log.txt",
        "pip-delete-this-directory.txt",
        "htmlcov/",
        ".tox/",
        ".nox/",
        ".coverage",
        ".coverage.*",
        ".cache",
        "nosetests.xml",
        "coverage.xml",
        "*.cover",
        "*.py,cover",
        ".hypothesis/",
        ".pytest_cache/",
        "cover/",
        "*.mo",
        "*.pot",
        "*.log",
        "local_settings.py",
        "db.sqlite3",
        "db.sqlite3-journal",
        "instance/",
        ".webassets-cache",
        ".scrapy",
        "docs/_build/",
        ".pybuilder/",
        "target/",
        ".ipynb_checkpoints",
        "profile_default/",
        "ipython_config.py",
        ".pdm.toml",
        ".pdm-python",
        ".pdm-build/",
        "__pypackages__/",
        "celerybeat-schedule",
        "celerybeat.pid",
        "*.sage.py",
        ".env",
        "env/",
        "venv/",
        "ENV/",
        "env.bak/",
        "venv.bak/",
        ".spyderproject",
        ".spyproject",
        ".ropeproject",
        "/site",
        ".mypy_cache/",
        ".dmypy.json",
        "dmypy.json",
        ".pyre/",
        ".pytype/",
        "cython_debug/"
      ],

  deps: [
    "@cdklabs/generative-ai-cdk-constructs",
    "cdk-aws-lambda-powertools-layer",
    "@aws-cdk/aws-lambda-python-alpha",
    "cdk-nag",
  ],

  // deps: [],                /* Runtime dependencies of this module. */
  // description: undefined,  /* The description is just a string that helps people understand the purpose of the package. */
  // devDeps: [],             /* Build dependencies for this module. */
  // packageName: undefined,  /* The "name" in package.json. */
});
project.projectBuild.preCompileTask.exec("bash utils/createapi.sh");
project.gitignore.addPatterns(".pnpm-store/");
project.addTask("schema", {
  description: "generate OpenAPI schemas",
  exec: "bash utils/createapi.sh",
});

//project.tasks.tryFind("test")?.exec("pytest src")
// project.addTask("build-lambda-api", {
//   description: "Build the API specs for lambda",
//
//   exec: "bash utils/createapi.sh"
//
//
// });
project.synth();
