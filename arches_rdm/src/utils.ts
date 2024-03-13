import type { Labellable } from "@/types";

const ALT_LABEL = "altLabel";
const PREF_LABEL = "prefLabel";

export const bestLabel = (item: Labellable, languageCode: string) => {
    const labelsInLang = item.labels.filter(l => l.language === languageCode);
    const bestLabel = (
        labelsInLang.find(l => l.valuetype === PREF_LABEL)
        ?? labelsInLang.find(l => l.valuetype === ALT_LABEL)
        ?? item.labels.find(l => l.valuetype === PREF_LABEL)
    );
    if (!bestLabel) {
        throw new Error();
    }
    return bestLabel;
};
