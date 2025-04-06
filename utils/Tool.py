import inspect

class Tool:
    """
    A class that represents a reusable tool meant for integration with agents.
    
    Attributes:
        name (str): The name of the tool.
        description (str): A brief description of the tool's purpose.
        func (callable): The function to be wrapped as a tool.
        args (list): A list of arguments for the tool.
        outputs (str or list): The return types of the wrapped function.
    """
    
    def __init__(self,
                 name: str,
                 description: str,
                 func: callable,
                 args: list = None,
                 outputs: str = None):
        self.name = name
        self.description = description
        self.func = func
        self.args = args if args is not None else []
        self.outputs = outputs if outputs is not None else []
    
    def to_string(self) -> str:
        """
        Returns a string representation of the tool, including its name, description, arguments and outputs.
        """
        args_str = ", ".join([
            f"{arg_name}: {arg_type}" for arg_name, arg_type in self.args
        ])

        return(
            f"Tool Name: {self.name}\n"
            f"Description: {self.description}\n"
            f"Arguments: {args_str}\n"
            f"Outputs: {self.outputs}"
        )
    
    def __call__(self, *args, **kwargs):
        """
        Calls the wrapped function with the provided arguments and keyword arguments.
        """
        return self.func(*args, **kwargs)
    
def tool(func):
    """
    A decorator to convert a function into a tool.
    """
    # get the function signature
    sig = inspect.signature(func)

    # extract param names and annotation pairs for inputs
    arguments = []
    for param in sig.parameters.values():
        annotation_name = (
            param.annotation.__name__ if hasattr(param.annotation, '__name__')
            else str(param.annotation)
        )
        arguments.append((param.name, annotation_name))

    # determine the return annotation
    return_annotation = sig.return_annotation
    if return_annotation is sig.empty:
        return_annotation = "No return annotation"
    else:
        ouputs = (
            return_annotation.__name__ if hasattr(return_annotation, '__name__')
            else str(return_annotation)
        )
    
    # use the docstring as the description
    description = func.__doc__ if func.__doc__ else "No description provided"

    # The function name is the name of the tool
    name = func.__name__

    # return the tool instance
    return Tool(
        name=name,
        description=description,
        func=func,
        args=arguments,
        outputs=ouputs
    )