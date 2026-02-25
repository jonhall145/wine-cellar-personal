declare module 'django' {
    const django: {
        gettext(msgid: string): string;
        ngettext(singular: string, plural: string, count: number): string;
        gettext_noop(msgid: string): string;
        pgettext(context: string, msgid: string): string;
        npgettext(
            context: string,
            singular: string,
            plural: string,
            count: number,
        ): string;
        interpolate(fmt: string, obj: Record<string, string>, named?: boolean): string;
    };
    export default django;
}
