from typing import cast
from pydantic import BaseModel as PydanticBaseModel
from pydantic.fields import FieldInfo


class BaseModel(PydanticBaseModel):
    class Config:
        """
        Changing default pydantic configuration to suit our needs for handling
        the messages of the communication protocols DIN SPEC 70121 and ISO 15118
        """

        # Allow input by alias or field name
        allow_population_by_field_name = True

        # Forbid extra attributes during model initialization
        extra = "forbid"

        # Validate the field if it's set on an instance (e.g. a field like
        # response code is added after the Model has been instantiated)
        validate_assignment = True


# from https://github.com/pydantic/pydantic/issues/897#issuecomment-1760587892
class NoValidator:
    def validate_python(self, args_kwargs, self_instance):
        model_fields = cast(dict[str, FieldInfo], self_instance.__pydantic_fields__)
        # print(model_fields)
        args = list(args_kwargs.args)
        mapping = dict(args_kwargs.kwargs) if args_kwargs.kwargs else dict()
        for field, info in model_fields.items():
            assert not info.init_var
            if not info.kw_only:
                mapping[field] = args.pop(0)
        for field, value in mapping.items():
            setattr(self_instance, field, value)


BaseModel.__pydantic_validator__ = NoValidator()
