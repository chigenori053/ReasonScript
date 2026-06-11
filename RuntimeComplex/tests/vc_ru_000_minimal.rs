use reasonscript_runtime_complex::ComplexReasonUnit;

#[test]
fn vc_ru_000_minimal_check() {
    let unit = ComplexReasonUnit::new("Initial Complex Unit");
    assert_eq!(unit.label, "Initial Complex Unit");
}
