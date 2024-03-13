export type Concept = {
    id: string,
    labels: Label[],
    narrower: Concept[],
};

export type Scheme = {
    id: string,
    labels: Label[],
    top_concepts: Concept[],
};

export type Label = {
    value: string,
    language: string,
    valuetype: "prefLabel" | "altLabel" | "unknown",
};

export type Labellable = Concept | Scheme;

// Should be imported from arches once it exposes types
export type Language = {
    code: string,
    default_direction: 'ltr' | 'rtl',
    id: number,
    isdefault: boolean,
    name: string,
    scope: string,
};
