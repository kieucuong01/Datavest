"""Typed request and response contracts for security-sensitive human APIs."""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class LoginRequestSchema(Schema):
    username = fields.String(validate=validate.Length(min=1, max=254))
    account = fields.String(validate=validate.Length(min=1, max=254))
    password = fields.String(required=True, validate=validate.Length(min=1, max=1024))
    turnstile_token = fields.String(allow_none=True, validate=validate.Length(max=4096))
    turnstile_clearance = fields.String(allow_none=True, validate=validate.Length(max=4096))

    @validates_schema
    def validate_identity(self, data, **kwargs):
        if not data.get("username") and not data.get("account"):
            raise ValidationError("username or account is required", field_name="username")


class RegisterRequestSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=254))
    code = fields.String(required=True, validate=validate.Length(min=1, max=32))
    username = fields.String(required=True, validate=validate.Length(min=3, max=30))
    password = fields.String(required=True, validate=validate.Length(min=1, max=1024))
    referral_code = fields.String(load_default="", validate=validate.Length(max=64))


class ResetPasswordRequestSchema(Schema):
    email = fields.Email(required=True, validate=validate.Length(max=254))
    code = fields.String(required=True, validate=validate.Length(min=1, max=32))
    new_password = fields.String(required=True, validate=validate.Length(min=1, max=1024))


class ChangePasswordRequestSchema(Schema):
    code = fields.String(required=True, validate=validate.Length(min=1, max=32))
    new_password = fields.String(required=True, validate=validate.Length(min=1, max=1024))


class UserInfoSchema(Schema):
    id = fields.Integer()
    username = fields.String()
    nickname = fields.String(allow_none=True)
    email = fields.Email(allow_none=True)
    avatar = fields.String(allow_none=True)
    timezone = fields.String(allow_none=True)
    role = fields.Raw(allow_none=True)


class LoginDataSchema(Schema):
    token = fields.String(required=True)
    userinfo = fields.Nested(UserInfoSchema, required=True)


class LoginResponseSchema(Schema):
    code = fields.Integer(required=True)
    msg = fields.String(required=True)
    data = fields.Nested(LoginDataSchema, allow_none=True)
