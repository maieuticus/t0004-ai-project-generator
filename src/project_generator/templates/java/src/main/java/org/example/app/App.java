package org.example.app;

public final class App {
    private App() {}

    public static String greeting() {
        return "Hello from project-java-starter!";
    }

    public static void main(String[] args) {
        System.out.println(greeting());
    }
}
