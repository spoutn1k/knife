//! The members of the recipe book and their rights, for admins.

use crate::api::{use_admin, use_api, use_me};
use crate::components::{ErrorBanner, KeyIcon, Loading, PenIcon, TrashIcon, confirm, use_mutation};
use dioxus::prelude::*;
use knife_core::MemberListing;
use knife_core::input::{MIN_PASSWORD_LEN, MemberPatch, NewMember};

#[component]
pub fn MemberList() -> Element {
    let api = use_api();
    let admin = use_admin();
    let me = use_me();
    let mut members = use_resource(move || {
        let api = api.clone();
        async move { api.members().await }
    });

    // Not an admin, or not known yet: the list would only be refused.
    let Some(me) = me else {
        return rsx! { Loading {} };
    };
    if !admin {
        return rsx! {
            h1 { "Members" }
            p { class: "muted", "Only admins manage members." }
        };
    }

    rsx! {
        h1 { "Members" }
        p { class: "muted",
            "Readers see the recipe book. Editors also change it, and admins manage this list."
        }
        match &*members.read() {
            None => rsx! { Loading {} },
            Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
            Some(Ok(list)) => rsx! {
                table { class: "data member-rows",
                    thead {
                        tr {
                            th { "Member" }
                            th { class: "right", "Editor" }
                            th { class: "right", "Admin" }
                            th { class: "actions", "Actions" }
                        }
                    }
                    tbody {
                        for member in list.clone() {
                            MemberRow {
                                key: "{member.uid}",
                                is_me: member.uid.0 == me.uid,
                                member,
                                on_changed: move |_| members.restart(),
                            }
                        }
                    }
                }
            },
        }
        AddMember { on_added: move |_| members.restart() }
    }
}

/// What a member row is showing.
#[derive(Clone, Copy, PartialEq)]
enum Mode {
    View,
    Rename,
    Password,
}

/// A member, whose rights are toggled in place. Admins cannot remove
/// themselves nor their own admin rights.
#[component]
fn MemberRow(member: MemberListing, is_me: bool, on_changed: EventHandler<()>) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    let mut mode = use_signal(|| Mode::View);
    let mut name = use_signal(|| member.display_name.clone());
    let mut password = use_signal(String::new);

    let save = {
        let (api, uid) = (api.clone(), member.uid.clone());
        move |patch: MemberPatch| {
            let (api, uid) = (api.clone(), uid.clone());
            mutation.run(async move {
                api.update_member(&uid, &patch).await?;
                mode.set(Mode::View);
                password.set(String::new());
                on_changed(());
                Ok(())
            });
        }
    };

    let rename = {
        let save = save.clone();
        move |e: FormEvent| {
            e.prevent_default();
            save(MemberPatch {
                display_name: Some(name()),
                ..Default::default()
            });
        }
    };
    let set_password = {
        let save = save.clone();
        move |e: FormEvent| {
            e.prevent_default();
            save(MemberPatch {
                password: Some(password()),
                ..Default::default()
            });
        }
    };
    let set_editor = {
        let save = save.clone();
        move |e: FormEvent| {
            save(MemberPatch {
                editor: Some(e.checked()),
                ..Default::default()
            })
        }
    };
    let set_admin = move |e: FormEvent| {
        save(MemberPatch {
            admin: Some(e.checked()),
            ..Default::default()
        })
    };

    let remove = {
        let (uid, display) = (member.uid.clone(), member.display_name.clone());
        move |_| {
            let question = format!(
                "Remove {display}? Their account is deleted, and they can no longer sign in."
            );
            if !confirm(&question) {
                return;
            }
            let (api, uid) = (api.clone(), uid.clone());
            mutation.run(async move {
                api.remove_member(&uid).await?;
                on_changed(());
                Ok(())
            });
        }
    };

    let cancel = {
        let original = member.display_name.clone();
        move |_| {
            name.set(original.clone());
            password.set(String::new());
            mode.set(Mode::View);
        }
    };
    let busy = *mutation.busy.read();

    rsx! {
        tr {
            if mode() == Mode::Rename {
                td { class: "editing", colspan: 4,
                    form { class: "row", onsubmit: rename,
                        input {
                            class: "grow",
                            required: true,
                            "aria-label": "Name",
                            value: "{name}",
                            oninput: move |e| name.set(e.value()),
                        }
                        button {
                            r#type: "submit",
                            disabled: busy || name() == member.display_name,
                            "Rename"
                        }
                        button { r#type: "button", class: "secondary", onclick: cancel, "Cancel" }
                    }
                }
            } else if mode() == Mode::Password {
                td { class: "editing", colspan: 4,
                    form { class: "row", onsubmit: set_password,
                        input {
                            class: "grow",
                            r#type: "password",
                            autocomplete: "new-password",
                            required: true,
                            minlength: "{MIN_PASSWORD_LEN}",
                            placeholder: "New password for {member.display_name}",
                            value: "{password}",
                            oninput: move |e| password.set(e.value()),
                        }
                        button { r#type: "submit", disabled: busy, "Set password" }
                        button { r#type: "button", class: "secondary", onclick: cancel, "Cancel" }
                    }
                }
            } else {
                td {
                    div { class: "member-name",
                        "{member.display_name}"
                        if is_me {
                            span { class: "muted", " (you)" }
                        }
                    }
                    div { class: "muted member-email",
                        {member.email.clone().unwrap_or_else(|| "no account".into())}
                    }
                }
                td { class: "right",
                    input {
                        r#type: "checkbox",
                        "aria-label": "{member.display_name} is an editor",
                        checked: member.editor,
                        disabled: busy,
                        onchange: set_editor,
                    }
                }
                td { class: "right",
                    input {
                        r#type: "checkbox",
                        "aria-label": "{member.display_name} is an admin",
                        checked: member.admin,
                        disabled: busy || is_me,
                        title: if is_me { "You cannot remove your own admin rights" } else { "" },
                        onchange: set_admin,
                    }
                }
                td { class: "actions",
                    span { class: "icon-buttons",
                        button {
                            class: "icon-button",
                            title: "Rename",
                            "aria-label": "Rename {member.display_name}",
                            onclick: move |_| mode.set(Mode::Rename),
                            PenIcon {}
                        }
                        button {
                            class: "icon-button",
                            title: "Set a new password",
                            "aria-label": "Set a new password for {member.display_name}",
                            onclick: move |_| mode.set(Mode::Password),
                            KeyIcon {}
                        }
                        if !is_me {
                            button {
                                class: "icon-button danger",
                                title: "Remove",
                                "aria-label": "Remove {member.display_name}",
                                disabled: busy,
                                onclick: remove,
                                TrashIcon {}
                            }
                        }
                    }
                }
            }
        }
        if mutation.error.read().is_some() {
            tr { class: "error-row",
                td { colspan: 4, {mutation.banner()} }
            }
        }
    }
}

/// Adds a member: an existing account by its email, or a new one when a
/// password is given.
#[component]
fn AddMember(on_added: EventHandler<()>) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    let mut email = use_signal(String::new);
    let mut name = use_signal(String::new);
    let mut password = use_signal(String::new);
    let mut editor = use_signal(|| false);
    let mut admin = use_signal(|| false);

    let submit = move |e: FormEvent| {
        e.prevent_default();
        let api = api.clone();
        let input = NewMember {
            email: email().trim().to_owned(),
            display_name: name(),
            password: Some(password()).filter(|p| !p.is_empty()),
            editor: editor(),
            admin: admin(),
        };
        mutation.run(async move {
            api.add_member(&input).await?;
            email.set(String::new());
            name.set(String::new());
            password.set(String::new());
            editor.set(false);
            admin.set(false);
            on_added(());
            Ok(())
        });
    };

    rsx! {
        form { class: "card stack", onsubmit: submit,
            h2 { "Add a member" }
            label {
                "Email"
                input {
                    r#type: "email",
                    autocomplete: "off",
                    required: true,
                    value: "{email}",
                    oninput: move |e| email.set(e.value()),
                }
            }
            label {
                "Name"
                input {
                    required: true,
                    value: "{name}",
                    oninput: move |e| name.set(e.value()),
                }
            }
            label {
                "Password"
                input {
                    r#type: "password",
                    autocomplete: "new-password",
                    minlength: "{MIN_PASSWORD_LEN}",
                    placeholder: "Only to create a new account",
                    value: "{password}",
                    oninput: move |e| password.set(e.value()),
                }
            }
            div { class: "row wrap",
                label { class: "check",
                    input {
                        r#type: "checkbox",
                        checked: editor(),
                        onchange: move |e| editor.set(e.checked()),
                    }
                    "Editor"
                }
                label { class: "check",
                    input {
                        r#type: "checkbox",
                        checked: admin(),
                        onchange: move |e| admin.set(e.checked()),
                    }
                    "Admin"
                }
            }
            {mutation.banner()}
            div { class: "row",
                button { r#type: "submit", disabled: *mutation.busy.read(), "Add" }
            }
        }
    }
}
