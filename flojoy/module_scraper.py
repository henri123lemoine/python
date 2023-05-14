import inspect

class FlojoyWrapper:
    CUSTOM_DOC_ADDITION = "-." * 36 + "\n\t"
    CUSTOM_DOC_ADDITION += (
        """The parameters of the function in this Flojoy wrapper are given below."""
    )
    CUSTOM_DOC_ADDITION += "\n\t" + "-." * 36 + "\n"
    INPUT_DEFAULT_DTYPE = "np.ndarray"
    FORBIDDEN_OPTIONAL_ARGS = ["x", "data", "kwargs", "comparator"]
    FORBIDDEN_TYPES = ["tuple", "array-like", "array_like", "function", "callable", "sequence"]

    def __init__(self, func, parameters, module, argument_names):
        # we'll use parameters to get the actual default values of the arguments
        # for generating the manifest
        self.name = func.__name__
        self.doc = func.__doc__
        self.arguments = argument_names
        self.optional_argument_dict = parameters
        self.module = module
        self.first_argument = argument_names[0]
        self.parameters = {
            self.first_argument: {"dtype": self.INPUT_DEFAULT_DTYPE, "optional": False}
        }
        self.data = f"from flojoy import DataContainer, flojoy\n"
        self.data += f"import {module.__name__}\n\n"
        self.data += f"@flojoy\ndef {self.name.upper()}(dc, params):\n\t"
        
        self.manifest = "COMMAND:\n\t- "

        self.process_docstring()

    def process_docstring(self):
        for idl, line in enumerate(self.doc.split("\n")):
            if "Returns" in line:
                break
        self.doc = "\n" + (
            "\n".join(
                [
                    ("\t" if (":" in line or "----------" in line) else "\t\t")
                    + line.lstrip(" ")
                    for line in self.doc.split("\n")[:idl]
                ]
            ).replace("\tParameters", self.CUSTOM_DOC_ADDITION + "\n" + "\tParameters")
        )

    def write_manifest(self, mtype):
        self.manifest += 'name: ' + self.name.lower().capitalize() + '\n'
        self.manifest += "\t\tkey: " + self.name.upper() + "\n"
        self.manifest += "\t\ttype: " + mtype + "\n"
        if self.parameters.keys() is not []:
            self.manifest += "\t\tparameters: \n\t\t"
            for param in self.parameters.keys():
                if param not in self.FORBIDDEN_OPTIONAL_ARGS:
                    try:
                        def_val = str(self.optional_argument_dict[param])
                    except:
                        def_val = "None"
                    self.manifest += (
                        f"\t{param}: \n"
                        + "\t\t\t\ttype: "
                        + str(self.parameters[param]["dtype"])
                        + "\n\t\t\t\tdefault: "
                        + ("" if def_val == "None" else def_val)
                        + " \n\t\t"
                    )

            self.manifest += "\t\t\n"
        self.manifest = self.manifest.replace("\t", "  ")

    def write_wrapper(self, mtype):
        if "callable" in self.doc:
            # print(
			# 	"#CANNOT PROCESS ",
			# 	self.name,
			# 	"since",
			# 	"callable",
			# 	"is not allowed ...",
			# )
            self.data = ""
            self.manifest=""
            return
        self.data += """'''"""
        self.data += self.doc
        self.data += "\t" + """'''""" + "\n"
        self.data += f"\treturn DataContainer(\n\t\tx=dc[0].y,\n\t\t"
        self.data += f"y={self.module.__name__}.{self.name}(\n\t\t\t{self.first_argument}=dc[0].y,\n\t\t\t"
        for idk, arg in enumerate(self.arguments):
            if arg not in self.FORBIDDEN_OPTIONAL_ARGS:
                dtype = ""
                try:  # try to read it from the inspect dictionary
                    dtype = type(self.optional_argument_dict[arg]).__name__
                except:
                    pass
                if dtype == "" or dtype == "NoneType":
                    for idl, line in enumerate(self.doc.split("\n")):
                        if f"{arg} :" in line:
                            dtype = (
                                line.split(":")[1]
                                .split(",")[0]
                                .strip()
                                .replace("}", "")
                                .replace("{", "")
                                .replace("(", "")
                                .replace(")", "")
                            )
                            break
                # now check for not allowed types after identifying them all correctly:
                if dtype in self.FORBIDDEN_TYPES:
                    # print(
                    #     "#CANNOT PROCESS ",
                    #     self.name,
                    #     "since",
                    #     dtype,
                    #     "is not allowed ...",
                    # )
                    self.data = ""
                    self.manifest=""
                    return
                if 'ndarray' in dtype:
                    dtype = 'np.ndarray'
                    self.data = "import numpy as np" + self.data
                self.data += f"{arg}=({dtype}(params['{arg}']) if params['{arg}'] != '' else None),\n\t\t"

                self.parameters[arg] = {"dtype": dtype, "optional": True}
                self.data += "\t" if idk < len(self.arguments) - 1 else ""
        self.data += ")\n\t)\n\n"
        self.write_manifest(mtype)

    def __repr__(self):
        retval = f"#{self.name}, {self.parameters}\n"
        retval += "#"+"-" * 72 + "\n#Wrapper\n" + "#"+"-" * 72 + "\n"
        retval += self.data + "\n"
        retval += "#"+"-" * 72 + "\n#Manifest\n" + "#"+"-" * 72 + "\n"
        retval += "#"+self.manifest.replace("\n","\n#") + "\n"
        return retval


def scrape_function(func):
    signature = inspect.signature(func)
    param_names = [p.name for p in signature.parameters.values()]
    default_optional_params = {
        k: val.default
        for k, val in signature.parameters.items()
        if val.default != inspect.Parameter.empty
    }
    return func, param_names, default_optional_params

if __name__ == "__main__":
    import os 
    from pathlib import Path
    import scipy
    import ast 

    MODULES_TO_SCRAPE = {"scipy": [scipy.signal, scipy.stats]}

    CWD = os.getcwd()
    MANIFEST_DIR = CWD / Path("MANIFEST")
    MANIFEST_DIR.mkdir(exist_ok=True)
    invalids = []
    valids = []
    for module in MODULES_TO_SCRAPE.keys():
        MODULE_DIR = Path(CWD) / Path(f"{module.upper()}")
        MODULE_DIR.mkdir(exist_ok=True)
        for submodule in MODULES_TO_SCRAPE[module]:
            submodule_name = submodule.__name__.split('.')[-1]
            NODE_DIR = MODULE_DIR/ Path(f"{submodule_name}")
            NODE_DIR.mkdir(exist_ok=True)

            for name, func in inspect.getmembers(submodule, inspect.isfunction):
                _, all_arg_names, default_optional_params = scrape_function(func)
                if (all_arg_names[0] == "x" or all_arg_names[0] == "data") and (
                    "y" not in all_arg_names and "plot" not in all_arg_names
                ):
                    fw = FlojoyWrapper(func, default_optional_params, submodule, all_arg_names)
                    fw.write_wrapper(f"{module.upper()}_{submodule_name.upper()}")
                    if fw.manifest != "" and fw.data != "" and "NoneType" not in fw.data:
                        try:
                            valid = ast.parse(fw.data)
                            with open(NODE_DIR / f"{fw.name}.py", "w") as fh:
                                fh.write(fw.data)
                            with open(MANIFEST_DIR / f"{fw.name}.manifest.yaml", "w") as fh:
                                fh.write(fw.manifest)
                            valids.append(fw.name)
                        except SyntaxError:
                            invalids.append(fw.name)
            with open(NODE_DIR/"__init__.py", "w") as fh:
                functions = "__all__ = [" 
                for name in valids:
                    functions += '"' + name.upper() + '", '
                functions = functions[:-2] + "]\n"
                fh.write(functions)