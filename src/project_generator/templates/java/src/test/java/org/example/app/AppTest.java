package org.example.app;

import static org.junit.jupiter.api.Assertions.assertEquals;
import org.junit.jupiter.api.Test;

class AppTest {
    @Test
    void greetingIsStable() {
        assertEquals("Hello from project-java-starter!", App.greeting());
    }
}
