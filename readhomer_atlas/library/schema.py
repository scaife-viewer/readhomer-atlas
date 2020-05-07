from django.db.models import Q

import django_filters
from graphene import Connection, Field, ObjectType, String, relay
from graphene.types import generic
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphene_django.utils import camelize

# from .models import Node as TextPart
from .models import (
    AudioAnnotation,
    ImageAnnotation,
    NamedEntity,
    Node,
    TextAlignment,
    TextAlignmentChunk,
    TextAnnotation,
    Token,
)
from .urn import URN
from .utils import (
    extract_version_urn_and_ref,
    filter_alignments_by_textparts,
    filter_via_ref_predicate,
    get_chunker,
    get_textparts_from_passage_reference,
)


# @@@ alias Node because relay.Node is quite different
TextPart = Node


class LimitedConnectionField(DjangoFilterConnectionField):
    """
    Ensures that queries without `first` or `last` return up to
    `max_limit` results.
    """

    @classmethod
    def connection_resolver(
        cls,
        resolver,
        connection,
        default_manager,
        max_limit,
        enforce_first_or_last,
        filterset_class,
        filtering_args,
        root,
        info,
        **resolver_kwargs,
    ):
        first = resolver_kwargs.get("first")
        last = resolver_kwargs.get("last")
        if not first and not last:
            resolver_kwargs["first"] = max_limit
        return super(LimitedConnectionField, cls).connection_resolver(
            resolver,
            connection,
            default_manager,
            max_limit,
            enforce_first_or_last,
            filterset_class,
            filtering_args,
            root,
            info,
            **resolver_kwargs,
        )


class PassageTextPartConnection(Connection):
    metadata = generic.GenericScalar()

    class Meta:
        abstract = True

    @staticmethod
    def generate_passage_urn(version, object_list):
        first = object_list[0]
        last = object_list[-1]

        if first == last:
            return first.get("urn")
        line_refs = [tp.get("ref") for tp in [first, last]]
        passage_ref = "-".join(line_refs)
        return f"{version.urn}{passage_ref}"

    def get_ancestor_metadata(self, version, obj):
        # @@@ this is currently the "first" ancestor
        # and we need to stop it at the version boundary for backwards
        # compatability with SV
        data = []
        if obj and obj.get_parent() != version:
            ancestor_urn = obj.urn.rsplit(".", maxsplit=1)[0]
            ancestor_ref = ancestor_urn.rsplit(":", maxsplit=1)[1]
            data.append(
                {
                    # @@@ proper name for this is ref or position?
                    "ref": ancestor_ref,
                    "urn": ancestor_urn,
                }
            )
        return data

    def get_sibling_metadata(self, version, all_queryset, start_idx, count):
        data = {}

        chunker = get_chunker(
            all_queryset, start_idx, count, queryset_values=["idx", "urn", "ref"]
        )
        previous_objects, next_objects = chunker.get_prev_next_boundaries()

        if previous_objects:
            data["previous"] = self.generate_passage_urn(version, previous_objects)

        if next_objects:
            data["next"] = self.generate_passage_urn(version, next_objects)
        return data

    def get_children_metadata(self, start_obj):
        data = []
        for tp in start_obj.get_children().values("ref", "urn"):
            # @@@ denorm lsb
            lsb = tp["ref"].rsplit(".", maxsplit=1)[-1]
            data.append(
                {
                    # @@@ proper name is lsb or position
                    "lsb": lsb,
                    "urn": tp.get("urn"),
                }
            )
        return data

    def resolve_metadata(self, info, *args, **kwargs):
        # @@@ resolve metadata.siblings|ancestors|children individually
        passage_dict = info.context.passage
        if not passage_dict:
            return

        urn = passage_dict["urn"]
        version = passage_dict["version"]

        refs = urn.rsplit(":", maxsplit=1)[1].split("-")
        first_ref = refs[0]
        last_ref = refs[-1]
        if first_ref == last_ref:
            start_obj = end_obj = version.get_descendants().get(ref=first_ref)
        else:
            start_obj = version.get_descendants().get(ref=first_ref)
            end_obj = version.get_descendants().get(ref=last_ref)

        data = {}
        siblings_qs = start_obj.get_siblings()
        start_idx = start_obj.idx
        chunk_length = end_obj.idx - start_obj.idx + 1
        data["ancestors"] = self.get_ancestor_metadata(version, start_obj)
        data["siblings"] = self.get_sibling_metadata(
            version, siblings_qs, start_idx, chunk_length
        )
        data["children"] = self.get_children_metadata(start_obj)
        return camelize(data)


# @@@ consider refactoring with TextPartsReferenceFilterMixin
class TextPartFilterSet(django_filters.FilterSet):
    reference = django_filters.CharFilter(method="reference_filter")

    def reference_filter(self, queryset, name, value):
        version_urn, ref = extract_version_urn_and_ref(value)
        start, end = ref.split("-")
        refs = [start]
        if end:
            refs.append(end)
        predicate = Q(ref__in=refs)
        queryset = queryset.filter(
            # @@@ this reference filter doesn't work because of
            # depth assumptions
            urn__startswith=version_urn,
            depth=len(start.split(".")) + 1,
        )
        return filter_via_ref_predicate(queryset, predicate)

    class Meta:
        model = TextPart
        fields = {
            "urn": ["exact", "startswith"],
            "ref": ["exact", "startswith"],
            "depth": ["exact", "lt", "gt"],
            "rank": ["exact", "lt", "gt"],
            "kind": ["exact"],
            "idx": ["exact"],
        }


class TextPartsReferenceFilterMixin:
    def _add_passage_to_context(self, reference):
        # @@@ instance.request is an alias for info.context and used to store
        # context data across filtersets
        self.request.passage = dict(urn=reference)

        version_urn, ref = extract_version_urn_and_ref(reference)
        try:
            version = TextPart.objects.get(urn=version_urn)
        except TextPart.DoesNotExist:
            raise Exception(f"{version_urn} was not found.")

        self.request.passage["version"] = version

    def get_lowest_textparts_queryset(self, value):
        self._add_passage_to_context(value)
        version = self.request.passage["version"]
        return get_textparts_from_passage_reference(value, version=version)


class PassageTextPartFilterSet(TextPartsReferenceFilterMixin, django_filters.FilterSet):
    reference = django_filters.CharFilter(method="reference_filter")

    class Meta:
        model = TextPart
        fields = []

    def reference_filter(self, queryset, name, value):
        return self.get_lowest_textparts_queryset(value)


class AbstractTextPartNode(DjangoObjectType):
    label = String()
    name = String()
    metadata = generic.GenericScalar()

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, **meta_options):
        meta_options.update(
            {
                "model": TextPart,
                "interfaces": (relay.Node,),
                "filterset_class": TextPartFilterSet,
            }
        )
        super().__init_subclass_with_meta__(**meta_options)

    def resolve_metadata(obj, *args, **kwargs):
        return camelize(obj.metadata)


class VersionNode(AbstractTextPartNode):
    text_alignment_chunks = LimitedConnectionField(lambda: TextAlignmentChunkNode)

    @classmethod
    def get_queryset(cls, queryset, info):
        return queryset.filter(kind="version").order_by("urn")

    def resolve_metadata(obj, *args, **kwargs):
        metadata = obj.metadata
        metadata.update(
            {"work_urn": URN(metadata["first_passage_urn"]).up_to(URN.WORK)}
        )
        return camelize(metadata)


class TextPartNode(AbstractTextPartNode):
    pass


class PassageTextPartNode(DjangoObjectType):
    label = String()

    class Meta:
        model = TextPart
        interfaces = (relay.Node,)
        connection_class = PassageTextPartConnection
        filterset_class = PassageTextPartFilterSet


class TreeNode(ObjectType):
    tree = generic.GenericScalar()

    def resolve_tree(obj, info, **kwargs):
        return obj


class TextAlignmentNode(DjangoObjectType):
    # @@@@ filter by the versions in a particular chunk
    metadata = generic.GenericScalar()

    class Meta:
        model = TextAlignment
        interfaces = (relay.Node,)
        filter_fields = ["name", "slug"]


class TextAlignmentChunkFilterSet(
    TextPartsReferenceFilterMixin, django_filters.FilterSet
):
    # @@@@ filter by the versions in a particular chunk
    reference = django_filters.CharFilter(method="reference_filter")

    class Meta:
        model = TextAlignmentChunk
        fields = ["idx", "alignment", "alignment__slug"]

    def reference_filter(self, queryset, name, value):
        textparts_queryset = self.get_lowest_textparts_queryset(value)
        return filter_alignments_by_textparts(textparts_queryset, queryset)


class TextAlignmentChunkNode(DjangoObjectType):
    items = generic.GenericScalar()

    class Meta:
        model = TextAlignmentChunk
        interfaces = (relay.Node,)
        filterset_class = TextAlignmentChunkFilterSet


class TextAnnotationNode(DjangoObjectType):
    data = generic.GenericScalar()

    class Meta:
        model = TextAnnotation
        interfaces = (relay.Node,)
        filter_fields = ["urn"]


class ImageAnnotationNode(DjangoObjectType):
    text_parts = LimitedConnectionField(lambda: TextPartNode)
    data = generic.GenericScalar()

    class Meta:
        model = ImageAnnotation
        interfaces = (relay.Node,)
        filter_fields = ["urn"]


class AudioAnnotationNode(DjangoObjectType):
    data = generic.GenericScalar()

    class Meta:
        model = AudioAnnotation
        interfaces = (relay.Node,)
        filter_fields = ["urn"]


class TokenFilterSet(django_filters.FilterSet):
    class Meta:
        model = Token
        fields = {"text_part__urn": ["exact", "startswith"]}


class TokenNode(DjangoObjectType):
    class Meta:
        model = Token
        interfaces = (relay.Node,)
        filterset_class = TokenFilterSet


class NamedEntityNode(DjangoObjectType):
    class Meta:
        filter_fields = ["urn"]
        model = NamedEntity
        interfaces = (relay.Node,)


class Query(ObjectType):
    version = relay.Node.Field(VersionNode)
    versions = LimitedConnectionField(VersionNode)

    text_part = relay.Node.Field(TextPartNode)
    text_parts = LimitedConnectionField(TextPartNode)

    # No passage_text_part endpoint available here like the others because we
    # will only support querying by reference.
    passage_text_parts = LimitedConnectionField(PassageTextPartNode)

    text_alignment_chunk = relay.Node.Field(TextAlignmentChunkNode)
    text_alignment_chunks = LimitedConnectionField(TextAlignmentChunkNode)

    text_annotation = relay.Node.Field(TextAnnotationNode)
    text_annotations = LimitedConnectionField(TextAnnotationNode)

    image_annotation = relay.Node.Field(ImageAnnotationNode)
    image_annotations = LimitedConnectionField(ImageAnnotationNode)

    audio_annotation = relay.Node.Field(AudioAnnotationNode)
    audio_annotations = LimitedConnectionField(AudioAnnotationNode)

    tree = Field(TreeNode, urn=String(required=True), up_to=String(required=False))

    token = relay.Node.Field(TokenNode)
    tokens = LimitedConnectionField(TokenNode)

    named_entity = relay.Node.Field(NamedEntityNode)
    named_entities = LimitedConnectionField(NamedEntityNode)

    def resolve_tree(obj, info, urn, **kwargs):
        return TextPart.dump_tree(
            root=TextPart.objects.get(urn=urn), up_to=kwargs.get("up_to")
        )
