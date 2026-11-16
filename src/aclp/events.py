"""Typed parameters for the standard ACLP events, generated from the pinned schema."""

from collections.abc import Mapping, Sequence
from typing import Literal, NotRequired, TypeAlias, TypedDict

__all__ = [
    "AgentFinishedParams",
    "AgentRef",
    "AgentRequestedParams",
    "AgentStartedParams",
    "Answer",
    "AnswerAccepted",
    "AnswerCancelled",
    "AnswerDeclined",
    "AudioContent",
    "CatalogChangedParams",
    "ClientInfo",
    "ClientRegisteredParams",
    "ClientUnregisteredParams",
    "ClientUpdatedParams",
    "Completion",
    "CompletionCancelled",
    "CompletionFailed",
    "CompletionSucceeded",
    "ConfigurationChangedParams",
    "ContentBlock",
    "ContextCompactionFinishedParams",
    "ContextCompactionRequestedParams",
    "ContextSourceLoadedParams",
    "DiscoveryAuth",
    "DiscoveryDocument",
    "EmbeddedResource",
    "EmbeddedResourceBlob",
    "EmbeddedResourceText",
    "ErrorOccurredParams",
    "EventMethod",
    "Failure",
    "HandoffFinishedParams",
    "HandoffRequestedParams",
    "ImageContent",
    "InputPayload",
    "InputSubmittedParams",
    "Interaction",
    "InteractionForm",
    "InteractionQuestion",
    "InteractionRequestedParams",
    "InteractionResolvedParams",
    "InteractionUrl",
    "JsonSchema",
    "JsonValue",
    "Message",
    "MessageEmittedParams",
    "MessageEmittingParams",
    "ModelChangedParams",
    "ModelCompletion",
    "ModelCompletionCancelled",
    "ModelCompletionFailed",
    "ModelCompletionSucceeded",
    "ModelFinishedParams",
    "ModelInput",
    "ModelMessage",
    "ModelOutput",
    "ModelRef",
    "ModelRequestedParams",
    "NotificationCreatedParams",
    "OAuthMetadata",
    "ObservedToolCall",
    "Operation",
    "OperationCapability",
    "OperationNetwork",
    "OperationResource",
    "OperationTool",
    "Payload",
    "PermissionOption",
    "PermissionRequestedParams",
    "PermissionResolvedParams",
    "PlanStep",
    "PlanUpdatedParams",
    "ProposedToolCall",
    "ResourceChangedParams",
    "ResourceContent",
    "ResourceLinkContent",
    "ResourceRef",
    "RunCancellationRequestedParams",
    "RunCompletion",
    "RunCompletionCancelled",
    "RunCompletionFailed",
    "RunCompletionInterrupted",
    "RunCompletionSucceeded",
    "RunFinishedParams",
    "RunFinishingParams",
    "RunPausedParams",
    "RunResumedParams",
    "RunStartedParams",
    "SessionEndedParams",
    "SessionStartedParams",
    "SettingChange",
    "SkillDefinition",
    "SoftwareRef",
    "Source",
    "TaskCreatedParams",
    "TaskFinishedParams",
    "TaskRef",
    "TaskSnapshot",
    "TaskUpdatedParams",
    "TextContent",
    "ToolBatchFinishedParams",
    "ToolCompletion",
    "ToolCompletionCancelled",
    "ToolCompletionDenied",
    "ToolCompletionFailed",
    "ToolCompletionSucceeded",
    "ToolCompletionUnknown",
    "ToolDefinition",
    "ToolFinishedItem",
    "ToolFinishedParams",
    "ToolRequestedParams",
    "ToolStartedParams",
    "UrlAnswer",
    "UrlAnswerAccepted",
    "UrlAnswerCancelled",
    "UrlAnswerDeclined",
    "Usage",
    "WorkspaceChangedParams",
    "WorkspaceRef",
]

JsonValue: TypeAlias = (
    "bool | int | float | str | Sequence[JsonValue] | Mapping[str, JsonValue] | None"
)

JsonSchema: TypeAlias = bool | Mapping[str, JsonValue]

EventMethod: TypeAlias = Literal[
    "agent.finished",
    "agent.requested",
    "agent.started",
    "catalog.changed",
    "client.registered",
    "client.unregistered",
    "client.updated",
    "configuration.changed",
    "context.compaction.finished",
    "context.compaction.requested",
    "context.source.loaded",
    "error.occurred",
    "handoff.finished",
    "handoff.requested",
    "input.submitted",
    "interaction.requested",
    "interaction.resolved",
    "message.emitted",
    "message.emitting",
    "model.changed",
    "model.finished",
    "model.requested",
    "notification.created",
    "permission.requested",
    "permission.resolved",
    "plan.updated",
    "resource.changed",
    "run.cancellation.requested",
    "run.finished",
    "run.finishing",
    "run.paused",
    "run.resumed",
    "run.started",
    "session.ended",
    "session.started",
    "task.created",
    "task.finished",
    "task.updated",
    "tool.batch.finished",
    "tool.finished",
    "tool.requested",
    "tool.started",
    "workspace.changed",
]


class TextContent(TypedDict):
    type: Literal["text"]
    text: str


class ImageContent(TypedDict):
    type: Literal["image"]
    data: str
    mimeType: str


class AudioContent(TypedDict):
    type: Literal["audio"]
    data: str
    mimeType: str


class ResourceLinkContent(TypedDict):
    type: Literal["resource_link"]
    uri: str
    name: str
    mimeType: NotRequired[str]


class EmbeddedResourceText(TypedDict):
    uri: str
    mimeType: NotRequired[str]
    text: str


class EmbeddedResourceBlob(TypedDict):
    uri: str
    mimeType: NotRequired[str]
    blob: str


EmbeddedResource: TypeAlias = EmbeddedResourceText | EmbeddedResourceBlob


class ResourceContent(TypedDict):
    type: Literal["resource"]
    resource: EmbeddedResource


ContentBlock: TypeAlias = (
    TextContent | ImageContent | AudioContent | ResourceLinkContent | ResourceContent
)


class Payload(TypedDict):
    content: list[ContentBlock]
    structuredContent: NotRequired[JsonValue]


class InputPayload(TypedDict):
    content: list[ContentBlock]
    structuredContent: NotRequired[JsonValue]


class Failure(TypedDict):
    message: str
    code: NotRequired[str]


class CompletionSucceeded(TypedDict):
    status: Literal["succeeded"]
    output: NotRequired[Payload]


class CompletionFailed(TypedDict):
    status: Literal["failed"]
    error: NotRequired[Failure]
    output: NotRequired[Payload]


class CompletionCancelled(TypedDict):
    status: Literal["cancelled"]
    reason: NotRequired[str]
    output: NotRequired[Payload]


Completion: TypeAlias = CompletionSucceeded | CompletionFailed | CompletionCancelled


class RunCompletionSucceeded(TypedDict):
    status: Literal["succeeded"]
    output: NotRequired[Payload]


class RunCompletionFailed(TypedDict):
    status: Literal["failed"]
    error: NotRequired[Failure]
    output: NotRequired[Payload]


class RunCompletionCancelled(TypedDict):
    status: Literal["cancelled"]
    reason: NotRequired[str]
    output: NotRequired[Payload]


class RunCompletionInterrupted(TypedDict):
    status: Literal["interrupted"]
    reason: str
    output: NotRequired[Payload]


RunCompletion: TypeAlias = (
    RunCompletionSucceeded | RunCompletionFailed | RunCompletionCancelled | RunCompletionInterrupted
)


class ToolCompletionSucceeded(TypedDict):
    status: Literal["succeeded"]
    output: NotRequired[Payload]


class ToolCompletionFailed(TypedDict):
    status: Literal["failed"]
    error: NotRequired[Failure]
    output: NotRequired[Payload]


class ToolCompletionCancelled(TypedDict):
    status: Literal["cancelled"]
    reason: NotRequired[str]
    output: NotRequired[Payload]


class ToolCompletionDenied(TypedDict):
    status: Literal["denied"]
    reason: NotRequired[str]


class ToolCompletionUnknown(TypedDict):
    status: Literal["unknown"]
    reason: NotRequired[str]
    output: NotRequired[Payload]


ToolCompletion: TypeAlias = (
    ToolCompletionSucceeded
    | ToolCompletionFailed
    | ToolCompletionCancelled
    | ToolCompletionDenied
    | ToolCompletionUnknown
)


class ObservedToolCall(TypedDict):
    id: NotRequired[str]
    name: str
    arguments: NotRequired[JsonValue]


class ProposedToolCall(TypedDict):
    id: NotRequired[str]
    name: str
    arguments: JsonValue


class ModelOutput(TypedDict):
    content: list[ContentBlock]
    structuredContent: NotRequired[JsonValue]
    calls: NotRequired[list[ProposedToolCall]]


class ModelCompletionSucceeded(TypedDict):
    status: Literal["succeeded"]
    output: NotRequired[ModelOutput]


class ModelCompletionFailed(TypedDict):
    status: Literal["failed"]
    error: NotRequired[Failure]
    output: NotRequired[ModelOutput]


class ModelCompletionCancelled(TypedDict):
    status: Literal["cancelled"]
    reason: NotRequired[str]
    output: NotRequired[ModelOutput]


ModelCompletion: TypeAlias = (
    ModelCompletionSucceeded | ModelCompletionFailed | ModelCompletionCancelled
)


class ToolDefinition(TypedDict):
    name: str
    description: NotRequired[str]
    inputSchema: JsonSchema
    outputSchema: NotRequired[JsonSchema]


class SkillDefinition(TypedDict):
    name: str
    description: NotRequired[str]
    uri: NotRequired[str]


class Source(TypedDict):
    kind: Literal["skill", "instructions", "memory", "resource"]
    name: str
    uri: NotRequired[str]


class AgentRef(TypedDict):
    id: NotRequired[str]
    name: NotRequired[str]


class ModelRef(TypedDict):
    name: str
    provider: NotRequired[str]


class ModelMessage(TypedDict):
    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: list[ContentBlock]
    structuredContent: NotRequired[JsonValue]
    calls: NotRequired[list[ProposedToolCall]]
    callId: NotRequired[str]


class ModelInput(TypedDict):
    messages: list[ModelMessage]
    view: Literal["complete", "partial"]


class Usage(TypedDict):
    inputTokens: NotRequired[int]
    outputTokens: NotRequired[int]
    cachedInputTokens: NotRequired[int]


class OperationTool(TypedDict):
    kind: Literal["tool"]
    call: ProposedToolCall


class OperationResource(TypedDict):
    kind: Literal["resource"]
    uri: str
    access: Literal["read", "write", "execute"]


class OperationNetwork(TypedDict):
    kind: Literal["network"]
    origin: str


class OperationCapability(TypedDict):
    kind: Literal["capability"]
    name: str


Operation: TypeAlias = OperationTool | OperationResource | OperationNetwork | OperationCapability


class PermissionOption(TypedDict):
    id: str
    label: str
    decision: Literal["allow", "deny"]
    scope: NotRequired[Literal["once", "session", "persistent"]]


class InteractionQuestion(TypedDict):
    kind: Literal["question"]
    message: str


class InteractionForm(TypedDict):
    kind: Literal["form"]
    message: str
    schema: JsonSchema


class InteractionUrl(TypedDict):
    kind: Literal["url"]
    message: str
    url: str


Interaction: TypeAlias = InteractionQuestion | InteractionForm | InteractionUrl


class AnswerAccepted(TypedDict):
    status: Literal["accepted"]
    value: JsonValue


class AnswerDeclined(TypedDict):
    status: Literal["declined"]


class AnswerCancelled(TypedDict):
    status: Literal["cancelled"]


Answer: TypeAlias = AnswerAccepted | AnswerDeclined | AnswerCancelled


class UrlAnswerAccepted(TypedDict):
    status: Literal["accepted"]


class UrlAnswerDeclined(TypedDict):
    status: Literal["declined"]


class UrlAnswerCancelled(TypedDict):
    status: Literal["cancelled"]


UrlAnswer: TypeAlias = UrlAnswerAccepted | UrlAnswerDeclined | UrlAnswerCancelled


class Message(TypedDict):
    id: NotRequired[str]
    content: list[ContentBlock]
    structuredContent: NotRequired[JsonValue]


class ToolFinishedItem(TypedDict):
    call: ObservedToolCall
    outcome: ToolCompletion


class PlanStep(TypedDict):
    id: NotRequired[str]
    title: str
    status: Literal["pending", "in_progress", "completed", "cancelled"]


class TaskSnapshot(TypedDict):
    id: str
    title: str
    detail: NotRequired[str]
    status: Literal["pending", "running", "blocked"]


class TaskRef(TypedDict):
    id: str
    title: NotRequired[str]


class ResourceRef(TypedDict):
    uri: str
    name: NotRequired[str]
    mimeType: NotRequired[str]


class WorkspaceRef(TypedDict):
    uri: str
    name: NotRequired[str]


class SettingChange(TypedDict):
    key: str
    value: NotRequired[JsonValue]


class SessionStartedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    reason: NotRequired[str]
    parentSessionId: NotRequired[str]


class SessionEndedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    reason: NotRequired[str]


class InputSubmittedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    content: list[ContentBlock]
    structuredContent: NotRequired[JsonValue]


class RunStartedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    input: NotRequired[InputPayload]
    resumesRunId: NotRequired[str]


class RunFinishingParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    output: NotRequired[Payload]


class RunFinishedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    outcome: RunCompletion


class ToolRequestedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    call: ProposedToolCall


class ToolStartedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    call: ObservedToolCall


class ToolFinishedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    call: ObservedToolCall
    outcome: ToolCompletion


class ContextCompactionRequestedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    reason: NotRequired[str]


class ContextCompactionFinishedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    outcome: Completion


class ContextSourceLoadedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    source: Source
    payload: NotRequired[Payload]


class CatalogChangedParams(TypedDict):
    sessionId: NotRequired[str]
    runId: NotRequired[str]
    agentId: NotRequired[str]
    catalog: Literal["tools", "skills"]
    entries: list[ToolDefinition] | list[SkillDefinition]


class ModelRequestedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    model: NotRequired[ModelRef]
    input: NotRequired[ModelInput]
    tools: NotRequired[list[ToolDefinition]]
    modelCallId: NotRequired[str]


class ModelFinishedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    model: NotRequired[ModelRef]
    modelCallId: NotRequired[str]
    outcome: ModelCompletion
    usage: NotRequired[Usage]


class PermissionRequestedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    requestId: NotRequired[str]
    operation: Operation
    options: list[PermissionOption]


class PermissionResolvedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    requestId: NotRequired[str]
    operation: Operation
    decision: Literal["allowed", "denied", "cancelled"]
    optionId: NotRequired[str]
    reason: NotRequired[str]


class InteractionRequestedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    requestId: NotRequired[str]
    interaction: Interaction


class InteractionResolvedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    requestId: NotRequired[str]
    interaction: Interaction
    response: Answer | UrlAnswer


class AgentRequestedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    agent: AgentRef
    childRunId: NotRequired[str]
    input: InputPayload


class AgentStartedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    agent: AgentRef
    childRunId: NotRequired[str]
    input: NotRequired[InputPayload]


class AgentFinishedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    agent: AgentRef
    childRunId: NotRequired[str]
    outcome: RunCompletion


HandoffRequestedParams = TypedDict(
    "HandoffRequestedParams",
    {
        "sessionId": str,
        "runId": NotRequired[str],
        "agentId": NotRequired[str],
        "from": AgentRef,
        "to": AgentRef,
        "input": NotRequired[InputPayload],
    },
)

HandoffFinishedParams = TypedDict(
    "HandoffFinishedParams",
    {
        "sessionId": str,
        "runId": NotRequired[str],
        "agentId": NotRequired[str],
        "from": AgentRef,
        "to": AgentRef,
        "outcome": Completion,
    },
)


class MessageEmittingParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    message: Message
    recipient: NotRequired[AgentRef]


class MessageEmittedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    message: Message
    recipient: NotRequired[AgentRef]


class RunCancellationRequestedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    reason: NotRequired[str]


class RunPausedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    reason: NotRequired[str]
    interactionId: NotRequired[str]


class RunResumedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    reason: NotRequired[str]
    interactionId: NotRequired[str]


class ToolBatchFinishedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    batchId: NotRequired[str]
    calls: list[ToolFinishedItem]


class PlanUpdatedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    steps: list[PlanStep]


class TaskCreatedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    task: TaskSnapshot


class TaskUpdatedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    task: TaskSnapshot


class TaskFinishedParams(TypedDict):
    sessionId: str
    runId: NotRequired[str]
    agentId: NotRequired[str]
    task: TaskRef
    outcome: Completion


class WorkspaceChangedParams(TypedDict):
    sessionId: NotRequired[str]
    runId: NotRequired[str]
    agentId: NotRequired[str]
    workspace: WorkspaceRef
    change: Literal["opened", "closed", "updated"]


class ResourceChangedParams(TypedDict):
    sessionId: NotRequired[str]
    runId: NotRequired[str]
    agentId: NotRequired[str]
    resource: ResourceRef
    change: Literal["created", "modified", "deleted", "renamed"]
    previousUri: NotRequired[str]


class ConfigurationChangedParams(TypedDict):
    sessionId: NotRequired[str]
    runId: NotRequired[str]
    agentId: NotRequired[str]
    changes: list[SettingChange]


class ModelChangedParams(TypedDict):
    sessionId: NotRequired[str]
    runId: NotRequired[str]
    agentId: NotRequired[str]
    model: ModelRef
    previousModel: NotRequired[ModelRef]


class NotificationCreatedParams(TypedDict):
    sessionId: NotRequired[str]
    runId: NotRequired[str]
    agentId: NotRequired[str]
    level: Literal["info", "warning", "error"]
    message: str
    code: NotRequired[str]


class ErrorOccurredParams(TypedDict):
    sessionId: NotRequired[str]
    runId: NotRequired[str]
    agentId: NotRequired[str]
    error: Failure
    operation: NotRequired[Operation]


class SoftwareRef(TypedDict):
    name: str
    version: NotRequired[str]


class ClientInfo(TypedDict):
    name: str
    version: NotRequired[str]
    harness: NotRequired[SoftwareRef]


class ClientRegisteredParams(TypedDict):
    client: ClientInfo
    events: list[str]


class ClientUpdatedParams(TypedDict):
    client: ClientInfo
    events: list[str]


class ClientUnregisteredParams(TypedDict):
    client: ClientInfo


class OAuthMetadata(TypedDict):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    device_authorization_endpoint: NotRequired[str]
    client_id: NotRequired[str]
    scopes_supported: NotRequired[list[str]]


class DiscoveryAuth(TypedDict):
    methods: list[Literal["token", "oauth"]]
    oauth: NotRequired[OAuthMetadata]


class DiscoveryDocument(TypedDict):
    name: NotRequired[str]
    endpoint: str
    auth: DiscoveryAuth
    events: list[str]
    requests: list[str]
