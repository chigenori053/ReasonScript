use runtime::frontend::lower;
use runtime::parser::parse;

#[test]
fn lowers_ast_to_hir() {
    let src = r#"
    goal scalar_math
    compute 1/2 + 3/4
    converge verify_numeric_result
    "#;
   let ast = parse(src);
   let hir = lower(&ast);

    assert_eq!(hir.nodes.len(), 3);
}
