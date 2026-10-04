use crate::api::use_api;
use crate::components::use_mutation;
use dioxus::prelude::*;

#[component]
pub fn SignIn() -> Element {
    let api = use_api();
    let mut email = use_signal(String::new);
    let mut password = use_signal(String::new);
    let mutation = use_mutation();

    let submit = move |e: FormEvent| {
        e.prevent_default();
        let api = api.clone();
        mutation.run(async move { api.sign_in(&email.peek(), &password.peek()).await });
    };

    rsx! {
        main { class: "narrow",
            h1 { class: "brand", "knife" }
            p { class: "muted", "The family recipe book. Sign in to continue." }
            form { class: "card stack", onsubmit: submit,
                label {
                    "Email"
                    input {
                        r#type: "email",
                        autocomplete: "username",
                        required: true,
                        value: "{email}",
                        oninput: move |e| email.set(e.value()),
                    }
                }
                label {
                    "Password"
                    input {
                        r#type: "password",
                        autocomplete: "current-password",
                        required: true,
                        value: "{password}",
                        oninput: move |e| password.set(e.value()),
                    }
                }
                {mutation.banner()}
                button { r#type: "submit", disabled: *mutation.busy.read(), "Sign in" }
            }
        }
    }
}
